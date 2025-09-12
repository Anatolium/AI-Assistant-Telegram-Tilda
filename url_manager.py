import os
import json
import requests
import logging
from typing import Optional

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = 'config.json'
NGROK_API = 'http://localhost:4040/api/tunnels'

def get_ngrok_url() -> Optional[str]:
    """Получает публичный URL от ngrok"""
    try:
        response = requests.get(NGROK_API)
        if response.status_code == 200:
            data = response.json()
            for tunnel in data['tunnels']:
                if tunnel['proto'] == 'https':
                    return tunnel['public_url']
        return None
    except Exception as e:
        logger.error(f"Error getting ngrok URL: {e}")
        return None

def update_config_url(url: str) -> bool:
    """Обновляет URL в конфигурационном файле"""
    try:
        config = {'base_url': url}
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return False

def get_config_url() -> Optional[str]:
    """Получает URL из конфигурационного файла"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('base_url')
    except Exception as e:
        logger.error(f"Error reading config: {e}")
    return None

def save_webhook_url(url):
    """Сохраняет URL вебхука в файл"""
    try:
        with open('webhook_url.txt', 'w') as f:
            f.write(url)
        return True
    except Exception as e:
        logger.error(f"Error saving webhook URL: {e}")
        return False

def get_webhook_url():
    """Получает URL вебхука из файла"""
    try:
        with open('webhook_url.txt', 'r') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Error reading webhook URL: {e}")
        return None

# Автоматическое обновление URL при запуске скрипта
if __name__ == '__main__':
    ngrok_url = get_ngrok_url()
    if ngrok_url:
        update_config_url(ngrok_url)
        logger.info(f"Updated base URL to: {ngrok_url}")
    else:
        logger.error("Failed to get ngrok URL")






