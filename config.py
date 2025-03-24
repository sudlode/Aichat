# config.py
import os
from dotenv import load_dotenv

# Завантажуємо змінні середовища з файлу .env
load_dotenv()

# Токен вашого Telegram бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Ваш OpenAI API ключ
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
