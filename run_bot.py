import subprocess
import time
import requests
import os
from dotenv import load_dotenv
from url_manager import save_webhook_url

# Загружаем переменные окружения
load_dotenv()

def get_ngrok_url():
    try:
        response = requests.get("http://localhost:4040/api/tunnels")
        url = response.json()["tunnels"][0]["public_url"]
        if url.startswith("https://"):
            return url
        return None
    except Exception as e:
        print(f"Ошибка при получении URL ngrok: {e}")
        return None

def run_ngrok():
    """Запускает ngrok туннель"""
    ngrok_cmd = f"ngrok http 5000 --authtoken {os.getenv('NGROK_AUTH_TOKEN')}"
    return subprocess.Popen(ngrok_cmd.split(), stdout=subprocess.PIPE)

def run_flask():
    """Запускает Flask сервер"""
    return subprocess.Popen(["python", "main.py"])

def main():
    print("🚀 ЗАПУСК СИСТЕМЫ World Class")
    print("=" * 40)
    print("1️⃣ Запускаем ngrok...")
    ngrok_process = subprocess.Popen(
        ["ngrok", "http", "5000"], 
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    )
    print("2️⃣ Ждём запуска ngrok (3 сек)...")
    time.sleep(3)
    print("3️⃣ Ждём готовности ngrok (2 сек)...")
    time.sleep(2)
    print("4️⃣ Получаем ngrok URL...")
    url = get_ngrok_url()
    if url:
        print(f"🌐 Ngrok URL: {url}")
        save_webhook_url(url)
        print("5️⃣ Обновляем webhook...")
        try:
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            response = requests.post(
                f"https://api.telegram.org/bot{bot_token}/setWebhook",
                json={"url": url}
            )
            if response.status_code == 200:
                print("✅ Webhook успешно обновлен")
            else:
                print(f"❌ Ошибка обновления webhook: {response.text}")
        except Exception as e:
            print(f"❌ Ошибка при обновлении webhook: {e}")
    else:
        print("❌ Не удалось получить URL ngrok")
    print("\n" + "=" * 50)
    print("🎯 СИСТЕМА ГОТОВА К РАБОТЕ!")
    print("=" * 50)
    print(f"📡 Flask будет запущен на: http://localhost:5000")
    if url:
        print(f"🌐 Внешний URL: {url}")
        print(f"🎯 Для виджета Tilda: {url}/website-chat")
    print("=" * 50)
    print("6️⃣ Запускаем Flask сервер...")
    print("(логи Flask будут показываться ниже)")
    print("-" * 50)
    try:
        import main
    except KeyboardInterrupt:
        print("\n🛑 Завершаем работу...")
        ngrok_process.terminate()
        print("✅ Системы остановлены")

if __name__ == "__main__":
    main()
