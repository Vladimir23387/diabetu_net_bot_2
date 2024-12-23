# stat_admin.py

import sqlite3
import logging
import json
from datetime import datetime

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Создание File Handler с правильной кодировкой
file_handler = logging.FileHandler('stat_admin.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

DB_NAME = 'stat_admin.db'

def initialize_db():
    """Инициализирует базу данных и создает необходимые таблицы."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                role TEXT,
                question_count INTEGER DEFAULT 0,
                promo_exhausted BOOLEAN DEFAULT FALSE
            )
        ''')
        # Таблица диалогов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dialogues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                role TEXT,
                message TEXT,
                timestamp TEXT
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("База данных stat_admin.db успешно инициализирована.")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")

def initialize_user(chat_id):
    """Инициализирует пользователя в базе данных."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE chat_id = ?', (chat_id,))
        user = cursor.fetchone()
        if not user:
            cursor.execute('INSERT INTO users (chat_id) VALUES (?)', (chat_id,))
            conn.commit()
            logger.info(f"Новый пользователь с chat_id {chat_id} добавлен в базу данных.")
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка при инициализации пользователя {chat_id}: {e}")

def log_dialogue(chat_id, role, message):
    """Логирует сообщение в таблицу dialogues."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        timestamp = datetime.utcnow().isoformat()
        cursor.execute('''
            INSERT INTO dialogues (chat_id, role, message, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (chat_id, role, message, timestamp))
        conn.commit()
        conn.close()
        logger.debug(f"Сообщение от {role} в chat_id {chat_id} записано: {message}")
    except Exception as e:
        logger.error(f"Ошибка при логировании диалога для chat_id {chat_id}: {e}")

def get_dialogue_history(chat_id, limit=10):
    """Получает историю диалога для указанного пользователя."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, message FROM dialogues
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT ?
        ''', (chat_id, limit))
        rows = cursor.fetchall()
        conn.close()
        history = [{'role': row[0], 'message': row[1]} for row in reversed(rows)]
        logger.debug(f"Получена история диалога для chat_id {chat_id}: {history}")
        return history
    except Exception as e:
        logger.error(f"Ошибка при получении истории диалога для chat_id {chat_id}: {e}")
        return []

def is_promo_exhausted(chat_id):
    """Проверяет, исчерпан ли лимит вопросов для пользователя с ролью 'user'."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT promo_exhausted FROM users WHERE chat_id = ?', (chat_id,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return bool(result[0])
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке promo_exhausted для chat_id {chat_id}: {e}")
        return False

def set_promo_exhausted(chat_id):
    """Устанавливает флаг promo_exhausted для пользователя."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET promo_exhausted = TRUE WHERE chat_id = ?', (chat_id,))
        conn.commit()
        conn.close()
        logger.info(f"Флаг promo_exhausted установлен для chat_id {chat_id}.")
    except Exception as e:
        logger.error(f"Ошибка при установке promo_exhausted для chat_id {chat_id}: {e}")
