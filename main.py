import os
import requests
import time
from flask import Flask, request, jsonify
import logging
from dotenv import load_dotenv
from functions import get_openai_assistant_reply, save_application_to_sheets, send_admin_notification, chat_with_assistant
from flask_cors import CORS
from url_manager import save_webhook_url, get_webhook_url, get_ngrok_url

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SECRET_COMMAND = "get_tunnel_url_worldclass_2024"  # Секретная команда
ALLOWED_ORIGINS = ['https://world-class-fitness-club.tilda.ws', 'https://tilda.ws', 'https://*.tilda.ws']

# Состояния пользователей
user_states = {}
widget_states = {}

app = Flask(__name__)

# Настройка CORS для Tilda
CORS(app, 
     origins=['*'],
     methods=['GET', 'POST', 'OPTIONS'],
     allow_headers=['Content-Type', 'ngrok-skip-browser-warning'],
     supports_credentials=False)

def send_message(chat_id, text, keyboard=None):
    """Отправка сообщения через Telegram API"""
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text
        }
        if keyboard:
            data['reply_markup'] = {
                'keyboard': keyboard,
                'resize_keyboard': True
            }
        response = requests.post(url, json=data, timeout=30)
        logger.info(f"Sent message to {chat_id}: {response.status_code}")
        return response.json()
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return None

@app.route('/', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        logger.info(f"Received: {data}")
        if 'message' in data and 'chat' in data['message']:
            message = data['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            logger.info(f"Message from {chat_id}: {text}")
            if text == SECRET_COMMAND:
                send_message(chat_id, "~")
                return 'ok'
            if text == '/start':
                keyboard = [['Быстрая запись'], ['Консультация']]
                send_message(chat_id, "Здравствуйте! Я ассистент World Class. Выберите действие:", keyboard)
            elif text == 'Быстрая запись':
                user_states[chat_id] = {'mode': 'booking', 'step': 'name', 'data': {}}
                send_message(chat_id, "Пожалуйста, введите ваше имя:")
            elif text == 'Консультация':
                user_states[chat_id] = {'mode': 'consult'}
                send_message(chat_id, "Задайте ваш вопрос по услугам клуба:")
            elif chat_id in user_states:
                state = user_states[chat_id]
                if state['mode'] == 'consult':
                    try:
                        logger.info(f"Getting AI response for user {chat_id}")
                        ai_response = get_openai_assistant_reply(chat_id, text)
                        keyboard = [['Быстрая запись'], ['Консультация']]
                        send_message(chat_id, ai_response, keyboard)
                    except Exception as e:
                        logger.error(f"Error getting AI response: {e}")
                        keyboard = [['Быстрая запись'], ['Консультация']]
                        send_message(chat_id, "Извините, произошла ошибка. Попробуйте задать вопрос позже.", keyboard)
                elif state['mode'] == 'booking':
                    step = state['step']
                    if step == 'name':
                        state['data']['name'] = text
                        state['step'] = 'phone'
                        send_message(chat_id, "Введите ваш номер телефона:")
                    elif step == 'phone':
                        state['data']['phone'] = text
                        state['step'] = 'service'
                        send_message(chat_id, "Какую услугу хотите получить?")
                    elif step == 'service':
                        state['data']['service'] = text
                        state['step'] = 'date'
                        send_message(chat_id, "Когда вам удобно прийти? (например, завтра в 14:00)")
                    elif step == 'date':
                        state['data']['date'] = text
                        state['step'] = 'master'
                        send_message(chat_id, "Выберите категорию мастера:\n1. Тренер\n2. Персональный тренер\n3. Ведущий тренер\n4. Эксперт")
                    elif step == 'master':
                        state['data']['master'] = text
                        try:
                            from datetime import datetime
                            booking_info = save_booking_data(state['data']['name'], state['data']['phone'], state['data']['service'], state['data']['date'], state['data']['master'])
                            keyboard = [['Быстрая запись'], ['Консультация']]
                            send_message(chat_id, booking_info, keyboard)
                            logger.info(f"Booking completed and saved: {state['data']}")
                        except Exception as e:
                            logger.error(f"Error saving booking: {e}")
                            send_message(chat_id, "Заявка принята! Мы свяжемся с вами для подтверждения.", [['Быстрая запись'], ['Консультация']])
                        del user_states[chat_id]
            else:
                keyboard = [['Быстрая запись'], ['Консультация']]
                send_message(chat_id, "Воспользуйтесь командой /start", keyboard)
        elif 'message' in data:
            return chat()
        return 'ok'
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return str(e), 500

@app.route('/health', methods=['GET'])
def health():
    return 'ok'

@app.route('/get_webhook_url', methods=['GET'])
def get_current_url():
    url = get_webhook_url()
    if url:
        return jsonify({'url': url})
    return jsonify({'error': 'URL not available'}), 500

@app.route('/website-chat', methods=['POST', 'OPTIONS'])
def website_chat():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, ngrok-skip-browser-warning')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        user_message = data.get('message', '')
        if not user_message:
            return jsonify({'status': 'error', 'message': 'No message provided'}), 400
        user_id = data.get('user_id', f"web_user_{request.remote_addr}")
        response = chat_with_assistant(user_message, user_id)
        result = {
            'status': 'success',
            'response': response,
            'message_id': data.get('message_id', ''),
            'timestamp': str(time.time())
        }
        response_obj = jsonify(result)
        response_obj.headers.add('Access-Control-Allow-Origin', '*')
        response_obj.headers.add('Access-Control-Allow-Headers', 'Content-Type, ngrok-skip-browser-warning')
        return response_obj
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_response = jsonify({
            'status': 'error',
            'message': f'Ошибка обработки запроса: {str(e)}'
        })
        error_response.headers.add('Access-Control-Allow-Origin', '*')
        error_response.headers.add('Access-Control-Allow-Headers', 'Content-Type, ngrok-skip-browser-warning')
        return error_response, 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        message = data.get('message', '')
        session_id = request.headers.get('X-Session-ID', 'default')
        logger.info(f"Chat message from widget session {session_id}: {message}")
        try:
            session_id = int(session_id)
        except Exception as e:
            logger.error(f"Error of session_id = int(session_id): {e}")
        try:
            ai_response = get_openai_assistant_reply(session_id, message)
            return jsonify({'response': ai_response})
        except Exception as e:
            logger.error(f"Error getting AI response for widget: {e}")
            return jsonify({'response': 'Извините, произошла ошибка. Пожалуйста, попробуйте позже.'}), 500
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        return jsonify({'error': str(e)}), 500

def save_booking_data(name: str, phone: str, service: str, datetime: str, master_category: str, comments: str = None):
    booking_data = {
        'name': name,
        'phone': phone,
        'service': service,
        'date': datetime,
        'master': master_category,
        'comment': comments if comments else ''
    }
    if save_application_to_sheets(booking_data):
        admin_text = f"""
НОВАЯ ЗАЯВКА через бота!

Имя: {booking_data['name']}
Телефон: {booking_data['phone']}
Услуга: {booking_data['service']}
Дата: {booking_data['date']}
Мастер: {booking_data['master']}
        """
        send_admin_notification(admin_text.strip())
        booking_info = f"""
Отлично! Ваша заявка принята:

Имя: {booking_data['name']}
Телефон: {booking_data['phone']}
Услуга: {booking_data['service']}
Дата: {booking_data['date']}
Мастер: {booking_data['master']}

Мы свяжемся с вами в ближайшее время для подтверждения записи!
        """
        return booking_info.strip()
    else:
        return "Извините, произошла ошибка при сохранении записи. Пожалуйста, попробуйте позже или свяжитесь с нами по телефону."

if __name__ == '__main__':
    try:
        print("🚀 ЗАПУСК ПРИЛОЖЕНИЯ")
        print("=" * 50)
        print("1️⃣ Инициализация OpenAI Assistant API...")
        from functions import initialize_openai, initialize_sheets
        if not initialize_openai():
            print("⚠️  Предупреждение: OpenAI Assistant API не инициализирован. Консультации будут недоступны.")
        print("2️⃣ Инициализация Google Sheets API...")
        initialize_sheets()
        print("3️⃣ Запуск Flask сервера...")
        print("=" * 50)
        print("🎯 СИСТЕМА ЗАПУЩЕНА!")
        print(f"📡 Flask API: http://localhost:5000")
        print(f"🤖 Telegram bot token: {BOT_TOKEN[:10]}...")
        print(f"🧠 OpenAI Assistant: ✅ Подключен")
        print("=" * 50)
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Остановка приложения пользователем...")
    except Exception as e:
        print(f"💥 КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        raise 
