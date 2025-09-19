# 🤖 Telegram-Tilda-AI-Assistant
ИИ-консультант фитнес-клуба "World Class".
Проект включает два бота на Telegram и Tilda.
Боты отвечают на вопросы клиентов через OpenAI и записывают заявки в Google Sheets.
Уведомление о заявке приходит в админ-группу Telegram.

---

## 🚀 Возможности

- Ответы на вопросы через OpenAI Assistant API.
- Запись на услуги фитнес-клуба (пошаговый диалог).
- Сохранение данных в Google Sheets:
  - Имя  
  - Телефон  
  - Услуга  
  - Дата и время  
  - Категория мастера  
  - Комментарий
- Уведомления администратору о новой заявке.
- Веб-виджет для интеграции на сайт (например, [Tilda](https://tilda.ru)).

---

## 🛠️ Технологии

- [Python 3.10+](https://www.python.org/)
- [Flask](https://flask.palletsprojects.com/) — обработка вебхуков и API для сайта  
- [Telegram Bot API](https://core.telegram.org/bots/api) — взаимодействие с Telegram  
- [Google Sheets API](https://developers.google.com/sheets/api) — хранение заявок  
- [OpenAI API](https://platform.openai.com/) — генерация ответов бота  
- [ngrok](https://ngrok.com/) — проброс локального сервера в интернет для тестирования вебхуков

---

## 📂 Структура проекта

fitness-club-assistant/
├── main.py                 # Flask-приложение
├── functions.py            # Логика (OpenAI, Sheets, уведомления)
├── url_manager.py          # Управление URL для вебхуков
├── update_webhook.py       # Установка вебхука Telegram
├── requirements.txt        # Зависимости
├── credentials.json        # (в .gitignore) ключ сервисного аккаунта Google
└── README.md

## 📊 Схема работы проекта

[Пользователь Telegram]
│
▼
[Сервер Telegram]
│ (вебхук)
▼
[Ngrok]
│ (туннель HTTPS → localhost:5000)
▼
[Flask (main.py)]
│───────────────► Обработка команд (/start, "Быстрая запись", "Консультация")
│───────────────► Вызов OpenAI (ответы на вопросы)
│───────────────► Сохранение данных бронирования
▼
[Google Sheets] ←───── Данные заявок

🔹 **Flask** — принимает запросы.  
🔹 **Ngrok** — делает сервер доступным из интернета.  
🔹 **Webhook Telegram** — извещает Flask о новых сообщениях.  
🔹 **OpenAI** — отвечает пользователю.  
🔹 **Google Sheets** — хранит заявки.  

👉 Веб-версия (виджет) работает аналогично.

## 📱 Telegram

• Создать бота, добавить его токен в .env
• Создать админ-группу для получения заявок, добавить ID группы в .env
• Назначить бота администратором в этой группе

## 🤖 OpenAI

• Получить API-токен, добавить его в .env
• Создать Ассистента, загрузить системный промпт и базу знаний
• Добавить идентификатор Ассистента в .env

## 📊 Подготовка Google Sheets

• Создайте таблицу с колонками:
Имя | Телефон | Услуга | Дата и время | Мастер | Комментарий

• Создать сервисный аккаунт в Google Cloud.
• Скачать credentials.json и поместить его в корень проекта.
• Дать доступ к таблице email сервисного аккаунта.
• Идентификатор таблицы Google Sheet добавить в .env

## 🌍️ Подготовка Ngrok

• Добавить AuthToken, полученный при установке ngrok, в .env

## ⚙️ Файл .env

TELEGRAM_BOT_TOKEN=<токен бота Телеграм>
TELEGRAM_GROUP_ID=<ID группы Телеграм, куда будут поступать заявки>
OPENAI_API_KEY=<API-токен OpenAI>
ASSISTANT_ID=<идентификатор ассистента OpenAI Assistant ID>
GOOGLE_SHEET_ID=<идентификатор таблицы Google Sheet>
NGROK_AUTH_TOKEN=<токен ngrok>

## 🚀 Запуск проекта

> python main.py
> start ngrok start --all --config=ngrok.yml
> python update_webhook.py

## 📌 Для работы консультанта на сайте виджет должен содержать HTTPS-ссылку, выданную при старте ngrok, e.g.

const API_URL = 'https://ced17de233c6.ngrok-free.app/website-chat';
