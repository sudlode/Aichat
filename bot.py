import logging
import openai
import sqlite3
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from datetime import datetime
from gtts import gTTS
from config import BOT_TOKEN, OPENAI_API_KEY

# Токени
openai.api_key = OPENAI_API_KEY

# Логування
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# База даних
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

# Створення таблиць
cursor.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, language TEXT DEFAULT 'українська', photo_limit INTEGER DEFAULT 100)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS history (user_id INTEGER, message TEXT, response TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS photo_requests (user_id INTEGER, photo_count INTEGER DEFAULT 0, last_reset DATETIME DEFAULT CURRENT_TIMESTAMP)""")
conn.commit()

# Функція перевірки реєстрації
def is_registered(user_id):
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

# Функція реєстрації
def register_user(user_id):
    cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute("INSERT INTO photo_requests (user_id, photo_count) VALUES (?, ?)", (user_id, 0))
    conn.commit()

# Генерація голосу
@dp.message_handler(commands=["voice"])
async def handle_voice_command(message: types.Message):
    if not is_registered(message.from_user.id):
        await message.reply("🔒 Ти не зареєстрований! Використай /register")
        return
    
    text = message.text[len("/voice "):].strip()
    if not text:
        await message.reply("📌 Напиши текст після команди /voice, і я зроблю голосове повідомлення.")
        return

    try:
        tts = gTTS(text=text, lang="uk")
        filename = f"voice_{message.from_user.id}.ogg"
        tts.save(filename)

        with open(filename, "rb") as voice_file:
            await message.reply_voice(voice_file)
        
        os.remove(filename)
    except Exception as e:
        await message.reply("❌ Сталася помилка при генерації голосового повідомлення.")
        logging.error(f"Помилка генерації голосу: {e}")

# Таблиця для промокодів
cursor.execute("""CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY, reward TEXT)""")
conn.commit()

# Додавання промокодів у базу (якщо вони ще не додані)
promo_codes = [
    ("FREE100", "Додаткові 100 фото на день!"),
    ("SECRET", "Секретний бонус 😏"),
    ("SHAURMA", "Знижка на шаурму 🌯 (але це жарт!)")
]

for code, reward in promo_codes:
    cursor.execute("INSERT OR IGNORE INTO promo_codes (code, reward) VALUES (?, ?)", (code, reward))
conn.commit()

# Обробка команди /promo
@dp.message_handler(commands=["promo"])
async def handle_promo(message: types.Message):
    if not is_registered(message.from_user.id):
        await message.reply("🔒 Ти не зареєстрований! Використай /register")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.reply("📌 Використання: /promo <код>")
        return

    code = args[1].upper()
    cursor.execute("SELECT reward FROM promo_codes WHERE code=?", (code,))
    result = cursor.fetchone()

    if result:
        reward = result[0]
        await message.reply(f"🎉 Промокод {code} активовано! {reward}")
    else:
        await message.reply("❌ Невірний або використаний промокод!")

# Запуск бота
if name == "__main__":
    executor.start_polling(dp, skip_updates=True)
