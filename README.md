# Telegram-бот "Нейро-консультант школы диабета"

Этот проект представляет собой Telegram-бота, разработанного для ответов на вопросы пользователей - больных сахарным диабетом.

## Структура Проекта

diabetu_net_bot_2/
├── bot.py
├── bot.log
├── kak_lechit_saharny_diabet.txt
├── knowledge_base.db
├── stat_admin.py
├── stat_admin.log
├── stat_admin.db
├── requirements.txt
└── README.md

bot.py: Основной код Telegram-бота.
bot.log: Логи работы бота.
kak_lechit_saharny_diabet.txt: Основная база знаний в doc.
knowledge_base.db: База знаний.
stat_admin.py: Служебный файл для фиксации логов и пользователей.
stat_admin.log: Логи вопросов и ответов.
stat_admin.db: База вопросов и ответов.
requirements.txt: Список библиотек.
README.md: Документация проекта.

## Установка

cd C:\diabetu_net_bot
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
python bot.py
