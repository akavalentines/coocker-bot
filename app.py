import os
import re
import asyncio
import sys
import traceback
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

# === ВРЕМЕННАЯ ЗАГЛУШКА REDIS ===
class FakeRedis:
    async def get(self, *args, **kwargs): return None
    async def setex(self, *args, **kwargs): return True
    async def delete(self, *args, **kwargs): return True
    async def exists(self, *args, **kwargs): return 0
    async def incr(self, *args, **kwargs): return 1
    async def expire(self, *args, **kwargs): return True

redis_client = FakeRedis()

ALLOWED_DOMAINS = ["t.me", "telegram.me", "youtube.com", "github.com"]
URL_PATTERN = re.compile(r"(https?://[^\s]+)")
SPAM_PATTERN = re.compile(r"(реклама|казино|заработок|крипта|скидки)", re.IGNORECASE)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()

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
        await bot.send_message(
            update.chat.id,
            f"Привет, {user.full_name}! Введи код **{captcha}** (просто напиши его в чат). У тебя 2 минуты."
        )

@dp.callback_query(lambda c: c.data == "new_captcha")
async def resend_captcha(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    new_captcha = generate_captcha()
    await callback.message.reply(f"Новый код: `{new_captcha}`")
    await callback.answer()

@dp.message()
async def anti_spam_handler(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    # Пока просто логируем, удаление выключено
    print(f"[DEBUG] Group message: {message.text}", file=sys.stderr, flush=True)
    # if has_forbidden_link(message.text) or has_spam_words(message.text):
    #     await message.delete()
    #     await message.answer("🚫 Спам запрещён!")

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    print("[DEBUG] start_cmd called", file=sys.stderr, flush=True)
    await message.answer("Антиспам-бот работает. Добавьте меня в группу с правами администратора.")
    print("[DEBUG] start_cmd finished", file=sys.stderr, flush=True)

# Flask app
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

@app.route('/webhook', methods=['POST'])
async def webhook():
    try:
        print("1. Webhook called", file=sys.stderr, flush=True)
        json_data = request.get_json()
        print("2. JSON received", file=sys.stderr, flush=True)
        update = types.Update.model_validate(json_data, context={"bot": bot})
        print("3. Update validated", file=sys.stderr, flush=True)
        await dp.feed_update(bot, update)
        print("4. Update fed to dispatcher", file=sys.stderr, flush=True)
        return "ok", 200
    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr, flush=True)
        return "error", 500

async def init():
    await bot.delete_webhook(drop_pending_updates=True)
    webhook_url = "https://coocker-bot.onrender.com/webhook"
    await bot.set_webhook(url=webhook_url, allowed_updates=dp.resolve_used_update_types())
    print(f"Webhook set to {webhook_url}", flush=True)

# Инициализация при старте
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(init())