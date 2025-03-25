import logging
import sqlite3
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
from gtts import gTTS
import openai
from dotenv import load_dotenv

# Завантаження змінних середовища
BOT_TOKEN = "7738138408:AAEMrBTn7b-G4I483n_f2b7ceKhl2eSRkdQ"  # Тимчасово! Потім поверніть os.getenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMINS = [1119767022]  # ЗАМІНІТЬ НА СВІЙ TELEGRAM ID

# Ініціалізація
openai.api_key = OPENAI_API_KEY
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Підключення до бази даних
def get_db_connection():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn

# Ініціалізація бази даних
def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Таблиця користувачів
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_banned BOOLEAN DEFAULT FALSE,
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_activity DATETIME,
                used_promo_codes TEXT DEFAULT ''
            )
        """)
        # Таблиця запитів на фото
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS photo_requests (
                user_id INTEGER PRIMARY KEY,
                count INTEGER DEFAULT 0,
                last_reset DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Таблиця промокодів
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                reward TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                used_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()

# Перевірка адміна
def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

# Клавіатура адмін-панелі
def admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("/users"))
    markup.add(KeyboardButton("/stats"))
    markup.add(KeyboardButton("/broadcast"))
    markup.add(KeyboardButton("/ban_user"))
    markup.add(KeyboardButton("/add_promo"))
    return markup

# Оновлення активності користувача
async def update_user_activity(user_id: int):
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()

# ================= КОМАНДИ ДЛЯ ВСІХ =================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await update_user_activity(message.from_user.id)
    with get_db_connection() as conn:
        # Перевірка чи користувач вже зареєстрований
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (message.from_user.id,))
        if not cursor.fetchone():
            # Реєстрація нового користувача
            cursor.execute(
                "INSERT INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                (message.from_user.id, message.from_user.username, 
                 message.from_user.first_name, message.from_user.last_name)
            )
            cursor.execute(
                "INSERT INTO photo_requests (user_id) VALUES (?)",
                (message.from_user.id,)
            )
            conn.commit()
    
    await message.answer("Привіт! Я твій бот. Використовуй /help для довідки.")

@dp.message(Command("voice"))
async def cmd_voice(message: types.Message):
    await update_user_activity(message.from_user.id)
    
    if len(message.text) < 7:
        await message.reply("Будь ласка, вкажи текст після команди /voice")
        return

    text = message.text[6:].strip()
    try:
        tts = gTTS(text=text, lang='uk')
        filename = f"voice_{message.from_user.id}.mp3"
        tts.save(filename)
        
        with open(filename, 'rb') as voice:
            await message.reply_voice(voice)
        
        os.remove(filename)
    except Exception as e:
        logger.error(f"Помилка генерації голосу: {e}")
        await message.reply("Сталася помилка при генерації голосового повідомлення")

@dp.message(Command("promo"))
async def cmd_promo(message: types.Message):
    await update_user_activity(message.from_user.id)
    
    if len(message.text.split()) < 2:
        await message.reply("ℹ️ Використовуйте: /promo [код]")
        return
    
    promo_code = message.text.split()[1].upper()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Перевірка промокоду
        cursor.execute("SELECT reward, is_active FROM promo_codes WHERE code = ?", (promo_code,))
        result = cursor.fetchone()
        
        if not result:
            await message.reply("❌ Невірний промокод!")
            return
        
        reward, is_active = result
        
        if not is_active:
            await message.reply("❌ Цей промокод вже не активний")
            return
        
        # Перевірка чи вже використовував
        cursor.execute("SELECT used_promo_codes FROM users WHERE user_id = ?", (message.from_user.id,))
        used_codes = cursor.fetchone()[0]
        
        if used_codes and promo_code in used_codes.split(','):
            await message.reply("⚠️ Ви вже використовували цей промокод")
            return
        
        # Застосовуємо промокод
        if "фото" in reward.lower():
            cursor.execute(
                "UPDATE photo_requests SET count = count + ? WHERE user_id = ?",
                (100 if "100" in reward else 50, message.from_user.id)
            )
        
        # Оновлюємо список використаних кодів
        new_used_codes = f"{used_codes},{promo_code}" if used_codes else promo_code
        cursor.execute(
            "UPDATE users SET used_promo_codes = ? WHERE user_id = ?",
            (new_used_codes, message.from_user.id)
        )
        
        # Оновлюємо лічильник використань
        cursor.execute(
            "UPDATE promo_codes SET used_count = used_count + 1 WHERE code = ?",
            (promo_code,)
        )
        
        conn.commit()
        await message.reply(f"🎉 Промокод застосовано! Отримано: {reward}")

# ================= АДМІН-КОМАНДИ =================

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.reply("⛔ Доступ заборонено!")
        return
    
    await message.reply(
        "🛠️ Вітаю в адмін-панелі!",
        reply_markup=admin_keyboard()
    )

@dp.message(Command("users"))
async def cmd_users(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, username, first_name, last_name, 
                   is_banned, last_activity 
            FROM users
            ORDER BY last_activity DESC
        """)
        users = cursor.fetchall()
    
    if not users:
        await message.reply("📭 Немає користувачів")
        return

    response = "📊 Користувачі бота:\n\n"
    for user in users:
        last_active = user["last_activity"] or "ніколи"
        status = "🔴 Забанений" if user["is_banned"] else "🟢 Активний"
        
        response += (
            f"👤 {user['first_name']} {user['last_name']} (@{user['username']})\n"
            f"🆔 ID: {user['user_id']}\n"
            f"📛 Статус: {status}\n"
            f"⏱ Остання активність: {last_active}\n"
            f"──────────────────\n"
        )
    
    await message.reply(response)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = TRUE")
        banned = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE last_activity > datetime('now', '-7 days')")
        active = cursor.fetchone()[0]
    
    await message.reply(
        f"📈 Статистика бота:\n\n"
        f"👥 Всього користувачів: {total}\n"
        f"🔴 Забанено: {banned}\n"
        f"🟢 Активних (за 7 днів): {active}"
    )

@dp.message(Command("ban_user"))
async def cmd_ban(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.reply("❌ Використовуйте: /ban_user [user_id]")
        return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET is_banned = TRUE WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
    
    await message.reply(f"✅ Користувач {user_id} заблокований!")

@dp.message(Command("add_promo"))
async def cmd_add_promo(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        _, code, reward = message.text.split(maxsplit=2)
        code = code.upper()
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO promo_codes (code, reward) VALUES (?, ?)",
                (code, reward)
            )
            conn.commit()
        
        await message.reply(f"✅ Промокод {code} додано! Нагорода: {reward}")
    except:
        await message.reply("❌ Використовуйте: /add_promo [код] [нагорода]")

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    text = message.text.replace('/broadcast', '').strip()
    if not text:
        await message.reply("Напишіть повідомлення після /broadcast")
        return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE is_banned = FALSE")
        users = cursor.fetchall()
        
        success = 0
        for (user_id,) in users:
            try:
                await bot.send_message(user_id, text)
                success += 1
            except:
                continue
    
    await message.reply(f"📢 Розсилка завершена! Доставлено: {success}/{len(users)}")

# ================= ЗАПУСК БОТА =================

async def main():
    init_db()  # Ініціалізація БД
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
    

