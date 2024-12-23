# bot.py

import openai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)
import logging
import os
import pandas as pd
from sqlalchemy import create_engine, inspect, text
import re
import json
from dotenv import load_dotenv
from docx import Document
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from openai.error import OpenAIError

# Импорт функций из stat_admin.py
import stat_admin

# Отключение предупреждения о симлинках (если используется Hugging Face)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Загрузка переменных окружения из файла .env
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler('bot.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Системный промпт для ассистента
SYSTEM_PROMPT = """
Ты — дружелюбный и внимательный нейро-помощник по имени Альт, специализирующийся на вопросах сахарного диабета.
Предоставляй подробные и точные медицинские консультации профессиональным и сострадательным тоном.
Не начинай ответы с приветствий. Результаты анализов на содержание глюкозы в крови предоставляй только в ммолях/л.
"""

embeddings = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')

def parse_document(doc_path: str) -> list:
    try:
        document = Document(doc_path)
        full_text = [para.text.strip() for para in document.paragraphs if para.text.strip()]
        logger.info(f"Документ {doc_path} успешно распарсен.")
        return full_text
    except Exception as e:
        logger.error(f"Ошибка при парсинге документа: {e}")
        return []

def update_knowledge_base(doc_path: str, db_name: str = 'knowledge_base.db') -> None:
    texts = parse_document(doc_path)
    if not texts:
        logger.error("Нет текста для обновления базы знаний.")
        return
    try:
        engine = create_engine(f'sqlite:///{db_name}')
        inspector = inspect(engine)

        if not inspector.has_table('knowledge'):
            with engine.connect() as conn:
                conn.execute(text('''
                    CREATE TABLE knowledge (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        content TEXT NOT NULL,
                        embedding TEXT NOT NULL,
                        tags TEXT
                    )
                '''))
            logger.info("Таблица 'knowledge' создана в базе данных.")

        data = []
        embeddings_list = embeddings.embed_documents(texts)
        for text_content, embedding in zip(texts, embeddings_list):
            data.append({
                'content': text_content,
                'embedding': json.dumps(embedding),
                'tags': json.dumps([])
            })

        df_new = pd.DataFrame(data)
        df_new.to_sql('knowledge', engine, if_exists='append', index=False)

        logger.info("База знаний успешно обновлена из документа.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении базы знаний: {e}")

def load_knowledge_base(db_name: str = 'knowledge_base.db') -> FAISS:
    try:
        engine = create_engine(f'sqlite:///{db_name}')
        df = pd.read_sql('knowledge', engine)
        df['tags'] = df['tags'].apply(lambda x: json.loads(x) if x else [])
        df['embedding'] = df['embedding'].apply(lambda x: json.loads(x) if x else [])
        texts = df['content'].tolist()
        vector_store = FAISS.from_texts(texts, embeddings)
        logger.info("База знаний загружена и индекс FAISS создан.")
        return vector_store
    except Exception as e:
        logger.error(f"Ошибка при загрузке базы знаний: {e}")
        return None

CHOOSING_ROLE = 1

class DiabetesBot:
    def __init__(self, telegram_token: str, doc_path: str, db_name: str = 'knowledge_base.db'):
        self.telegram_token = telegram_token
        self.doc_path = doc_path
        self.db_name = db_name
        self.knowledge_store = None

        logger.info("Обновление базы знаний из документа.")
        update_knowledge_base(self.doc_path, self.db_name)
        self.knowledge_store = load_knowledge_base(self.db_name)
        if self.knowledge_store is None:
            logger.error("Не удалось загрузить базу знаний.")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        chat_id = update.effective_chat.id
        stat_admin.initialize_user(chat_id)
        logger.info(f"Пользователь {chat_id} инициализирован.")

        welcome_message = (
            "Пожалуйста, выберите вашу роль:\n"
            "1. Администратор\n"
            "2. Пользователь\n\n"
            "Введите `1` для Администратора или `2` для Пользователя."
        )
        await update.message.reply_text(welcome_message)
        return CHOOSING_ROLE

    async def choose_role(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        chat_id = update.effective_chat.id
        user_response = update.message.text.strip()
        logger.info(f"Пользователь {chat_id} выбрал: {user_response}")

        if user_response == '1':
            context.user_data['role'] = 'administrator'
            await update.message.reply_text(
                "Вы выбрали роль Администратора.\n"
                "Вы можете задавать неограниченное количество вопросов.\n"
                "Введите `/stop` для завершения сеанса."
            )
            return ConversationHandler.END
        elif user_response == '2':
            context.user_data['role'] = 'user'
            context.user_data['question_count'] = 0
            await update.message.reply_text(
                "Вы выбрали роль Пользователя.\n"
                "Вы можете задать до 5 вопросов.\n"
                "Введите ваш первый вопрос или `/stop` для завершения сеанса."
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text("Пожалуйста, введите `1` для Администратора или `2` для Пользователя.")
            return CHOOSING_ROLE

    async def stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        chat_id = update.effective_chat.id
        await update.message.reply_text("Сеанс завершен. Вы можете начать новый сеанс с помощью команды `/start`.")
        logger.info(f"Сеанс пользователя {chat_id} завершен.")
        return ConversationHandler.END

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text = (
            "Доступные команды:\n"
            "/start - Начать сеанс и выбрать роль\n"
            "/stop - Завершить сеанс\n"
            "/help - Показать доступные команды"
        )
        await update.message.reply_text(help_text)
        logger.info(f"Пользователь {update.effective_chat.id} вызвал /help.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            chat_id = update.effective_chat.id
            user_message = update.message.text.strip()

            # Важно: убедиться, что роли "assistant_summary" или "assistant_full" не используются нигде.
            # Ниже при логировании используем только "assistant" или "user" для OpenAI, а в stat_admin.log_dialogue можно любые строки
            # потому что это не идет в OpenAI, это просто внутренняя БД.

            # Здесь мы просто проверяем роль пользователя
            role = context.user_data.get('role', 'user')

            # Проверка лимита вопросов для 'user'
            if role == 'user':
                context.user_data['question_count'] = context.user_data.get('question_count', 0) + 1
                if context.user_data['question_count'] > 5:
                    await update.message.reply_text("Вы превысили лимит в 5 вопросов. Введите `/stop` для завершения сеанса.")
                    return

            # Логирование вопроса пользователя
            stat_admin.log_dialogue(chat_id, "user", user_message)

            # Здесь напишите логику получения ответа от OpenAI
            # Например, сразу сделать запрос к OpenAI и получить ответ ассистента
            # с учетом SYSTEM_PROMPT и пользовательского сообщения.
            # Главное — роли должны быть 'system', 'assistant' или 'user'.
            # Если вам нужно сделать резюме или полный ответ, используйте модель как раньше,
            # но не используйте нестандартные роли в сообщениях.
            # Просто сохраняйте ответы в переменные и отправляйте их пользователю.

            # Пример простого ответа (без резюме/полный):
            # Это просто пример, здесь вы должны адаптировать логику к вашим нуждам.

            # Запрос к OpenAI
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=2000,
                    temperature=0
                )

                assistant_reply = response.choices[0].message['content'].strip()
                await update.message.reply_text(assistant_reply)

                # Логирование ответа ассистента
                stat_admin.log_dialogue(chat_id, "assistant", assistant_reply)

            except OpenAIError as e:
                logger.error(f"Ошибка при обработке сообщения через OpenAI API: {e}")
                error_message = "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже."
                await update.message.reply_text(error_message)

        except Exception as e:
            logger.exception(f"Неизвестная ошибка в handle_message: {e}")
            await update.message.reply_text("Произошла непредвиденная ошибка.")

    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        user_role = context.user_data.get('role', 'user')

        if user_role == 'user' and context.user_data.get('question_count', 0) >= 5:
            await update.message.reply_text("Вы завершили сеанс вопросов. Для начала нового сеанса введите `/start`.")
        else:
            await update.message.reply_text("Извините, я не понимаю эту команду. Введите `/help` для списка доступных команд.")

    async def error_handler_method(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error(msg="Exception while handling an update:", exc_info=context.error)
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("Извините, произошла ошибка при обработке вашего запроса.")

    def run(self) -> None:
        application = ApplicationBuilder().token(self.telegram_token).build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                CHOOSING_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.choose_role)]
            },
            fallbacks=[CommandHandler("stop", self.stop)]
        )

        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("stop", self.stop))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.add_handler(MessageHandler(filters.COMMAND, self.unknown_command))
        application.add_error_handler(self.error_handler_method)

        logger.info("Бот запущен и работает...")
        application.run_polling()

def main():
    stat_admin.initialize_db()
    doc_path = r'C:\diabetu_net_bot\kak_lechit_saharny_diabet.docx'
    bot = DiabetesBot(
        telegram_token=TELEGRAM_BOT_TOKEN,
        doc_path=doc_path,
        db_name='knowledge_base.db'
    )
    bot.run()

if __name__ == '__main__':
    main()
