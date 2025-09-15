import os
import time
import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from functions import (
    get_openai_assistant_reply,
    save_application_to_sheets,
    send_admin_notification,
    chat_with_assistant,
    initialize_openai,
    initialize_sheets
)
from url_manager import get_webhook_url

# ==============================
# БАЗОВЫЕ НАСТРОЙКИ
# ==============================

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

SECRET_COMMAND = "get_tunnel_url_worldclass_2024"

MAIN_KEYBOARD = [["Быстрая запись"], ["Консультация"]]

# Состояния пользователей (Telegram)
user_states = {}

# Flask
app = Flask(__name__)
CORS(app,
     origins=["https://world-class-fitness-club.tilda.ws"],
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "ngrok-skip-browser-warning"])


# ==============================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================

def send_message(chat_id: int, text: str, keyboard=None):
    """Отправка сообщения через Telegram API"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    if keyboard:
        payload["reply_markup"] = {"keyboard": keyboard, "resize_keyboard": True}

    try:
        response = requests.post(url, json=payload, timeout=30).json()
        if not response.get("ok", False):
            logger.error(f"Telegram API error: {response}")
        return response
    except requests.RequestException as e:
        logger.error(f"Error sending message: {e}")
        return None


def save_booking_data(name, phone, service, datetime, master_category, comments=None):
    booking_data = {
        "name": name,
        "phone": phone,
        "service": service,
        "date": datetime,
        "master": master_category,
        "comment": comments or ""
    }

    if save_application_to_sheets(booking_data):
        # Уведомляем администратора
        admin_text = f"""
НОВАЯ ЗАЯВКА через бота!

Имя: {booking_data['name']}
Телефон: {booking_data['phone']}
Услуга: {booking_data['service']}
Дата: {booking_data['date']}
Мастер: {booking_data['master']}
        """
        send_admin_notification(admin_text.strip())

        # Сообщение пользователю
        return f"""
Отлично! Ваша заявка принята:

Имя: {booking_data['name']}
Телефон: {booking_data['phone']}
Услуга: {booking_data['service']}
Дата: {booking_data['date']}
Мастер: {booking_data['master']}

Мы свяжемся с вами в ближайшее время для подтверждения записи!
        """.strip()
    else:
        return "Извините, произошла ошибка при сохранении записи. Попробуйте позже."


# ==============================
# ROUTES
# ==============================

@app.route("/", methods=["POST"])
def webhook():
    """Webhook для Telegram"""
    try:
        data = request.get_json()
        logger.info(f"Telegram update: {data}")

        if "message" not in data:
            return "ok"

        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        # Секретная команда
        if text == SECRET_COMMAND:
            send_message(chat_id, "~")
            return "ok"

        # Старт
        if text == "/start":
            send_message(chat_id,
                         "Здравствуйте! Я ассистент World Class. Выберите действие:",
                         MAIN_KEYBOARD)
            return "ok"

        # Быстрая запись
        if text == "Быстрая запись":
            user_states[chat_id] = {"mode": "booking", "step": "name", "data": {}}
            send_message(chat_id, "Пожалуйста, введите ваше имя:")
            return "ok"

        # Консультация
        if text == "Консультация":
            user_states[chat_id] = {"mode": "consult"}
            send_message(chat_id, "Задайте ваш вопрос по услугам клуба:")
            return "ok"

        # Работаем с состояниями
        if chat_id in user_states:
            state = user_states[chat_id]

            if state["mode"] == "consult":
                try:
                    ai_response = get_openai_assistant_reply(chat_id, text)
                    send_message(chat_id, ai_response, MAIN_KEYBOARD)
                except Exception as e:
                    logger.error(f"AI error: {e}")
                    send_message(chat_id,
                                 "Извините, произошла ошибка. Попробуйте позже.",
                                 MAIN_KEYBOARD)

            elif state["mode"] == "booking":
                step = state["step"]
                if step == "name":
                    state["data"]["name"] = text
                    state["step"] = "phone"
                    send_message(chat_id, "Введите ваш номер телефона:")
                elif step == "phone":
                    state["data"]["phone"] = text
                    state["step"] = "service"
                    send_message(chat_id, "Какую услугу хотите получить?")
                elif step == "service":
                    state["data"]["service"] = text
                    state["step"] = "date"
                    send_message(chat_id, "Когда вам удобно прийти? (например, завтра в 14:00)")
                elif step == "date":
                    state["data"]["date"] = text
                    state["step"] = "master"
                    send_message(chat_id,
                                 "Выберите категорию мастера:\n1. Тренер\n2. Персональный тренер\n3. Ведущий тренер\n4. Эксперт")
                elif step == "master":
                    state["data"]["master"] = text
                    state["step"] = "comment"
                    send_message(chat_id,
                                 "Если хотите, добавьте комментарий (например, особые пожелания). Можно оставить пустым:")
                elif step == "comment":
                    state["data"]["comment"] = text if text.strip() else ""
                    try:
                        booking_info = save_booking_data(
                            state["data"]["name"],
                            state["data"]["phone"],
                            state["data"]["service"],
                            state["data"]["date"],
                            state["data"]["master"],
                            state["data"]["comment"]
                        )
                        send_message(chat_id, booking_info, MAIN_KEYBOARD)
                        logger.info(f"Booking saved: {state['data']}")
                    except Exception as e:
                        logger.error(f"Booking error: {e}")
                        send_message(chat_id,
                                     "Заявка принята! Мы свяжемся с вами для подтверждения.",
                                     MAIN_KEYBOARD)
                    finally:
                        user_states.pop(chat_id, None)

        else:
            send_message(chat_id, "Воспользуйтесь командой /start", MAIN_KEYBOARD)

        return "ok"

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return str(e), 500


@app.route("/website-chat", methods=["POST", "OPTIONS"])
def website_chat():
    """Чат-виджет для сайта"""
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, ngrok-skip-browser-warning")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response

    try:
        data = request.get_json() or {}
        user_message = data.get("message", "")
        if not user_message:
            return jsonify({"status": "error", "message": "No message provided"}), 400

        user_id = data.get("user_id", f"web_user_{request.remote_addr}")
        response_text = chat_with_assistant(user_message, user_id)

        result = {
            "status": "success",
            "response": response_text,
            "message_id": data.get("message_id", ""),
            "timestamp": str(time.time())
        }

        response_obj = jsonify(result)
        response_obj.headers.add("Access-Control-Allow-Origin", "*")
        response_obj.headers.add("Access-Control-Allow-Headers", "Content-Type, ngrok-skip-browser-warning")
        return response_obj

    except Exception as e:
        logger.error(f"Website chat error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return "ok"


@app.route("/get_webhook_url", methods=["GET"])
def get_current_url():
    url = get_webhook_url()
    return jsonify({"url": url}) if url else (jsonify({"error": "URL not available"}), 500)


# ==============================
# MAIN
# ==============================

if __name__ == "__main__":
    try:
        print("🚀 ЗАПУСК ПРИЛОЖЕНИЯ")
        print("=" * 50)

        print("1️⃣ Инициализация OpenAI Assistant API...")
        if not initialize_openai():
            print("⚠️ OpenAI Assistant API не инициализирован.")

        print("2️⃣ Инициализация Google Sheets API...")
        initialize_sheets()

        print("3️⃣ Запуск Flask сервера...")
        print("=" * 50)
        print("🎯 СИСТЕМА ЗАПУЩЕНА!")
        print(f"📡 Flask API: http://localhost:5000")
        print(f"🤖 Telegram bot token: {BOT_TOKEN[:10]}...")
        print("=" * 50)

        app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

    except KeyboardInterrupt:
        print("\n🛑 Остановка приложения пользователем...")
    except Exception as e:
        print(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        raise
