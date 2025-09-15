import os
import requests
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
import time
import logging
from openai import OpenAI

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# --- ИНИЦИАЛИЗАЦИЯ OPENAI ASSISTANT ---
openai_client = None

def initialize_openai():
    """Инициализация OpenAI Assistant API"""
    global openai_client
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
        openai_client = OpenAI(
            api_key=api_key,
            default_headers={"OpenAI-Beta": "assistants=v2"}
        )
        logger.info("OpenAI Assistant API успешно инициализирован")
        assistant_id = os.getenv('ASSISTANT_ID')
        if assistant_id:
            try:
                assistant = openai_client.beta.assistants.retrieve(assistant_id)
                logger.info(f"Assistant найден: {assistant.name}")
            except Exception as e:
                logger.warning(f"Предупреждение: Не удалось найти Assistant {assistant_id}: {e}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации OpenAI: {str(e)}")
        openai_client = None
        return False

# --- ИНИЦИАЛИЗАЦИЯ GOOGLE SHEETS ---
sheets_service = None

def initialize_sheets():
    """Инициализация Google Sheets API"""
    global sheets_service
    try:
        credentials_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Файл учетных данных Google Sheets не найден: {credentials_path}")
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=scopes
        )
        sheets_service = build('sheets', 'v4', credentials=creds)
        logger.info("Google Sheets API успешно инициализирован")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации Google Sheets: {str(e)}")
        sheets_service = None
        return False

# Вызываем инициализацию при импорте
initialize_openai()
initialize_sheets()

# --- ИНИЦИАЛИЗАЦИЯ TELEGRAM ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
TELEGRAM_API_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}'

# --- ХРАНЕНИЕ THREAD_ID ДЛЯ КАЖДОГО ПОЛЬЗОВАТЕЛЯ ---
user_threads = {}  # user_id (str/int) -> thread_id (str)
web_threads = {}  # Сохраняем thread_id для веб-пользователей
web_message_counts = {}  # Счетчик сообщений для каждого thread

# --- ФУНКЦИИ ---
def save_application_to_sheets(data: dict):
    """
    Сохраняет заявку в Google Таблицу.
    Колонки:
    A - Имя
    B - Телефон
    C - Желаемая услуга
    D - Дата и время желаемой записи
    E - Категория мастера
    F - Комментарии/пожелания
    """
    try:
        logger.info(f"Attempting to save to Google Sheets: {data}")
        row = [
            data.get('name', ''),
            "'" + data.get('phone', ''),
            data.get('service', ''),
            data.get('date', ''),
            data.get('master', ''),
            data.get('comment', '')
        ]
        range_name = 'Лист1!A:F'
        value_input_option = 'USER_ENTERED'
        insert_data_option = 'INSERT_ROWS'
        value_range_body = {
            'values': [row]
        }
        spreadsheet_id = os.getenv('GOOGLE_SHEET_ID')
        if not spreadsheet_id:
            raise ValueError("GOOGLE_SHEET_ID не найден в переменных окружения")
        result = sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption=value_input_option,
            insertDataOption=insert_data_option,
            body=value_range_body
        ).execute()
        logger.info(f"Successfully saved to Google Sheets: {result}")
        return True
    except Exception as e:
        logger.error(f"Error in save_application_to_sheets: {str(e)}", exc_info=True)
        return False

def send_admin_notification(text: str):
    """
    Отправляет уведомление в служебный Telegram-чат.
    """
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            'chat_id': ADMIN_CHAT_ID,
            'text': text,
            'parse_mode': "HTML"
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Error in send_admin_notification: {str(e)}")

def remove_formatting(text: str) -> str:
    """
    Удаляет символы форматирования из текста
    """
    text = text.replace('**', '')
    text = text.replace('†', '')
    text = text.replace('【', '')
    text = text.replace('】', '')
    return text

def get_openai_assistant_reply(user_id: int, message: str) -> str:
    """
    Получает ответ от OpenAI Assistant
    """
    try:
        logger.info(f"Processing message from user {user_id}: {message}")
        models = openai_client.models.list()
        logger.info(f"Successfully connected to OpenAI. Available models: {[model.id for model in models]}")
        assistant = openai_client.beta.assistants.retrieve(os.getenv('ASSISTANT_ID'))
        logger.info(f"Successfully retrieved assistant: {assistant.id}")
        if user_id not in user_threads:
            logger.info(f"Creating new thread for user {user_id}")
            thread = openai_client.beta.threads.create()
            user_threads[user_id] = thread.id
            logger.info(f"Created new thread: {thread.id}")
        else:
            logger.info(f"Using existing thread for user {user_id}: {user_threads[user_id]}")
        logger.info(f"Sending message to thread {user_threads[user_id]}")
        openai_client.beta.threads.messages.create(
            thread_id=user_threads[user_id],
            role="user",
            content=message
        )
        logger.info("Message sent successfully")
        logger.info(f"Starting assistant run with ID {assistant.id}")
        run = openai_client.beta.threads.runs.create(
            thread_id=user_threads[user_id],
            assistant_id=assistant.id
        )
        logger.info(f"Run created: {run.id}")
        max_wait = 30
        start_time = time.time()
        while time.time() - start_time < max_wait:
            run = openai_client.beta.threads.runs.retrieve(
                thread_id=user_threads[user_id],
                run_id=run.id
            )
            logger.info(f"Run status: {run.status}")
            if run.status == "completed":
                logger.info("Run completed, retrieving messages")
                messages = openai_client.beta.threads.messages.list(
                    thread_id=user_threads[user_id]
                )
                assistant_message = messages.data[0].content[0].text.value
                assistant_message = remove_formatting(assistant_message)
                logger.info(f"Got response: {assistant_message[:50]}...")
                return assistant_message
            elif run.status == "requires_action":
                logger.info("🔧 Run requires action, handling function calls")
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    logger.info(f"📞 Function call: {function_name}")
                    if function_name == "save_booking_data":
                        try:
                            import json
                            from datetime import datetime
                            function_args = json.loads(tool_call.function.arguments)
                            logger.info(f"📋 Function arguments: {function_args}")
                            sheets_data = {
                                'name': function_args.get('name', ''),
                                'phone': function_args.get('phone', ''),
                                'service': function_args.get('service', ''),
                                'date': function_args.get('datetime', ''),
                                'master': function_args.get('master_category', ''),
                                'comment': function_args.get('comments', ''),
                                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            success = save_application_to_sheets(sheets_data)
                            if success:
                                admin_text = f"""
🤖 НОВАЯ ЗАЯВКА через Telegram бота!

👤 Имя: {function_args.get('name', '')}
📞 Телефон: {function_args.get('phone', '')}
💅 Услуга: {function_args.get('service', '')}
📅 Дата: {function_args.get('datetime', '')}
👨‍🎨 Мастер: {function_args.get('master_category', '')}
💬 Комментарий: {function_args.get('comments', 'Нет')}
⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                                """
                                send_admin_notification(admin_text.strip())
                                tool_outputs.append({
                                    "tool_call_id": tool_call.id,
                                    "output": "✅ Запись успешно сохранена в Google Sheets! Мы свяжемся с вами для подтверждения."
                                })
                                logger.info("✅ Booking data saved successfully")
                            else:
                                tool_outputs.append({
                                    "tool_call_id": tool_call.id,
                                    "output": "❌ Ошибка при сохранении записи. Мы получили ваши данные и свяжемся с вами."
                                })
                                logger.error("❌ Failed to save booking data")
                        except Exception as e:
                            logger.error(f"❌ Error processing save_booking_data: {e}")
                            tool_outputs.append({
                                "tool_call_id": tool_call.id,
                                "output": f"❌ Ошибка: {str(e)}"
                            })
                if tool_outputs:
                    run = openai_client.beta.threads.runs.submit_tool_outputs(
                        thread_id=user_threads[user_id],
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )
                    logger.info("📤 Tool outputs submitted, continuing run...")
            elif run.status in ["failed", "cancelled", "expired"]:
                logger.error(f"Run failed with status: {run.status}")
                return "Извините, произошла ошибка при обработке запроса"
            time.sleep(1)
        logger.warning("Request timed out")
        return "Извините, время ожидания ответа истекло. Попробуйте задать вопрос еще раз."
    except Exception as e:
        logger.error(f"Error in get_openai_assistant_reply: {str(e)}", exc_info=True)
        return "Извините, произошла ошибка при обработке запроса. Попробуйте позже."

def clean_assistant_response(text: str) -> str:
    """Очистка ответа от технических символов и ссылок"""
    import re
    text = re.sub(r'【[^】]*】', '', text)
    text = re.sub(r'\[[^\]]*†[^\]]*\]', '', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'†', '', text)
    text = re.sub(r'‡', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def chat_with_assistant(message: str, user_id: str = None):
    """Общение с OpenAI Assistant с поддержкой Function Calling и памятью диалога"""
    if not openai_client:
        return "Извините, Assistant API временно недоступен. Воспользуйтесь быстрой записью или обратитесь к администратору."
    try:
        assistant_id = os.getenv('ASSISTANT_ID')
        if not assistant_id:
            return "Ошибка конфигурации Assistant API."
        MAX_MESSAGES = 12
        if user_id and user_id in web_threads:
            message_count = web_message_counts.get(user_id, 0)
            if message_count >= MAX_MESSAGES:
                thread = openai_client.beta.threads.create()
                thread_id = thread.id
                web_threads[user_id] = thread_id
                web_message_counts[user_id] = 0
            else:
                thread_id = web_threads[user_id]
        else:
            thread = openai_client.beta.threads.create()
            thread_id = thread.id
            if user_id:
                web_threads[user_id] = thread_id
                web_message_counts[user_id] = 0
        if user_id:
            web_message_counts[user_id] = web_message_counts.get(user_id, 0) + 1
        openai_client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message
        )
        run = openai_client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        import time
        while run.status in ['queued', 'in_progress', 'cancelling']:
            time.sleep(1)
            run = openai_client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            if run.status == 'requires_action':
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    import json
                    function_args = json.loads(tool_call.function.arguments)
                    if function_name == "save_booking_data":
                        sheets_data = {
                            'name': function_args.get('name', ''),
                            'phone': function_args.get('phone', ''),
                            'service': function_args.get('service', ''),
                            'date': function_args.get('datetime', ''),
                            'master': function_args.get('master_category', ''),
                            'comment': function_args.get('comments', ''),
                            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        success = save_application_to_sheets(sheets_data)
                        if success:
                            admin_text = f"""
🌐 НОВАЯ ЗАЯВКА через веб-виджет!

👤 Имя: {function_args.get('name', '')}
📞 Телефон: {function_args.get('phone', '')}
💅 Услуга: {function_args.get('service', '')}
📅 Дата: {function_args.get('datetime', '')}
👨‍🎨 Мастер: {function_args.get('master_category', '')}
💬 Комментарий: {function_args.get('comments', 'Нет')}
⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                            """
                            send_admin_notification(admin_text.strip())
                        result = {
                            "success": success,
                            "message": "Запись успешно сохранена!" if success else "Ошибка при сохранении записи"
                        }
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": str(result)
                        })
                run = openai_client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )
        if run.status == 'completed':
            messages = openai_client.beta.threads.messages.list(
                thread_id=thread_id
            )
            for message in messages.data:
                if message.role == "assistant":
                    raw_response = message.content[0].text.value
                    cleaned_response = clean_assistant_response(raw_response)
                    return cleaned_response
        return "Извините, произошла ошибка при обработке вашего запроса."
    except Exception as e:
        print(f"Ошибка при общении с Assistant: {str(e)}")
        return "Извините, произошла ошибка при обработке вашего запроса." 
