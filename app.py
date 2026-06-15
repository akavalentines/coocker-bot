import os
import re
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from flask import Flask, request
from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Токен не найден в .env")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Конфигурация антиспама
ALLOWED_DOMAINS = ["t.me", "telegram.me", "youtube.com", "github.com"]
NEW_USER_MUTE_SECONDS = 300
CAPTCHA_TIMEOUT = 120
MAX_SPAM_ATTEMPTS = 3

URL_PATTERN = re.compile(r"(https?://[^\s]+)")
SPAM_PATTERN = re.compile(r"(реклама|казино|заработок|крипта|скидки)", re.IGNORECASE)

# Инициализация бота
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
redis_client = None

def has_forbidden_link(text: str) -> bool:
    if not text:
        return False
    urls = URL_PATTERN.findall(text)
    for url in urls:
        domain = re.sub(r"https?://(www\.)?", "", url).split("/")[0].lower()
        if domain not in ALLOWED_DOMAINS:
            return True
    return False

def has_spam_words(text: str) -> bool:
    return bool(SPAM_PATTERN.search(text))

def generate_captcha() -> str:
    import random, string
    return ''.join(random.choices(string.digits, k=4))

@dp.chat_member()
async def on_user_join(update: types.ChatMemberUpdated):
    if update.new_chat_member.status == "member":
        user = update.new_chat_member.user
        captcha = generate_captcha()
        await redis_client.setex(f"captcha:{user.id}", CAPTCHA_TIMEOUT, captcha)
        await redis_client.setex(f"mute:{update.chat.id}:{user.id}", NEW_USER_MUTE_SECONDS, "1")
        await bot.send_message(
            update.chat.id,
            f"Привет, {user.full_name}! Введи код **{captcha}** (просто напиши его в чат). У тебя 2 минуты."
        )

@dp.callback_query(lambda c: c.data == "new_captcha")
async def resend_captcha(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await redis_client.exists(f"captcha:{user_id}"):
        new_captcha = generate_captcha()
        await redis_client.setex(f"captcha:{user_id}", CAPTCHA_TIMEOUT, new_captcha)
        await callback.message.reply(f"Новый код: `{new_captcha}`")
    await callback.answer()

@dp.message()
async def anti_spam_handler(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    user_id = message.from_user.id
    chat_id = message.chat.id

    stored_captcha = await redis_client.get(f"captcha:{user_id}")
    if stored_captcha:
        if message.text and message.text.strip() == stored_captcha:
            await redis_client.delete(f"captcha:{user_id}")
            await redis_client.delete(f"mute:{chat_id}:{user_id}")
            await message.reply("✅ Капча пройдена! Можно писать.")
            return
        else:
            await message.delete()
            await message.reply("❌ Неверная капча. Нажмите кнопку для новой.")
            return

    if await redis_client.exists(f"mute:{chat_id}:{user_id}"):
        await message.delete()
        return

    if has_forbidden_link(message.text) or has_spam_words(message.text):
        await message.delete()
        spam_count = await redis_client.incr(f"spam:{user_id}")
        await redis_client.expire(f"spam:{user_id}", 86400)
        if spam_count >= MAX_SPAM_ATTEMPTS:
            await bot.ban_chat_member(chat_id, user_id)
            await message.answer(f"🚫 {message.from_user.full_name} забанен за спам.")
        else:
            await redis_client.setex(f"mute:{chat_id}:{user_id}", 600, "1")
            await message.answer(f"⚠️ Спам запрещён. Мут 10 минут (нарушение {spam_count}/{MAX_SPAM_ATTEMPTS})")
        return

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Антиспам-бот работает. Добавьте меня в группу с правами администратора.")

# Flask для вебхука
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

@app.route('/webhook', methods=['POST'])
async def webhook():
    json_data = request.get_json()
    update = types.Update.model_validate(json_data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return "ok", 200

async def init():
    global redis_client
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    await bot.delete_webhook(drop_pending_updates=True)
    webhook_url = f"https://coocker-bot.onrender.com/webhook"
    await bot.set_webhook(url=webhook_url, allowed_updates=dp.resolve_used_update_types())
    print(f"Webhook set to {webhook_url}", flush=True)

# Инициализация при старте
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(init())