import requests
import os
import time
from dotenv import load_dotenv
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_ngrok_url():
    """Получает публичный URL ngrok"""
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get("http://localhost:4040/api/tunnels")
            if response.status_code == 200:
                data = response.json()
                for tunnel in data["tunnels"]:
                    if tunnel["proto"] == "https":
                        return tunnel["public_url"]
            logger.info(f"Попытка получить URL ngrok ({attempt + 1}/{max_attempts})")
            time.sleep(1)
        except:
            time.sleep(1)
    return None

def main():
    # Загружаем переменные окружения
    load_dotenv()
    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    # Получаем URL ngrok
    logger.info("Получаем URL ngrok...")
    ngrok_url = get_ngrok_url()
    if not ngrok_url:
        logger.error("Не удалось получить URL ngrok")
        return False
    # Формируем URL для webhook
    webhook_url = f"{ngrok_url}/"
    logger.info(f"Webhook URL: {webhook_url}")
    # Обновляем webhook
    telegram_url = f"https://api.telegram.org/bot{telegram_bot_token}/setWebhook"
    response = requests.post(telegram_url, json={"url": webhook_url})
    if response.status_code == 200:
        logger.info("Webhook успешно обновлен")
        return True
    else:
        logger.error(f"Ошибка при обновлении webhook: {response.text}")
        return False

if __name__ == "__main__":
    main()
