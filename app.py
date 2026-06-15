import os
import re
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Токен не найден в .env")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Конфигурация антиспама (без Redis пока)
ALLOWED_DOMAINS = ["t.me", "telegram.me", "youtube.com", "github.com"]
NEW_USER_MUTE_SECONDS = 300
CAPTCHA_TIMEOUT = 120
MAX_SPAM_ATTEMPTS = 3

URL_PATTERN = re.compile(r"(https?://[^\s]+)")
SPAM_PATTERN = re.compile(r"(реклама|казино|заработок|крипта|скидки)", re.IGNORECASE)

# Заглушка Redis (временная, чтобы бот работал)
class FakeRedis:
    async def get(self, key):
        return None
    async def setex(self, key, time, value):
        pass
    async def delete(self, key):
        pass
    async def exists(self, key):
        return 0
    async def incr(self, key):
        return 1
    async def expire(self, key, time):
        pass

redis_client = FakeRedis()

# Инициализация бота
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
        # Временно не сохраняем в Redis, просто отправляем сообщение
        await bot.send_message(
            update.chat.id,
            f"Привет, {user.full_name}! Введи код **{captcha}** (просто напиши его в чат). У тебя 2 минуты. (Внимание: Redis временно отключен, капча не проверяется)"
        )

@dp.callback_query(lambda c: c.data == "new_captcha")
async def resend_captcha(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    new_captcha = generate_captcha()
    await callback.message.reply(f"Новый код: `{new_captcha}` (Redis временно отключен, капча не сохраняется)")
    await callback.answer()

@dp.message()
async def anti_spam_handler(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    # Временно игнорируем спам-проверку, только логируем
    print(f"Сообщение в группе: {message.text}", flush=True)
    # Если хотите, можете временно отключить удаление
    # Просто пропускаем все сообщения
    return

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Антиспам-бот работает. Добавьте меня в группу с правами администратора. (Режим тестирования, Redis отключен)")

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
    # Удаляем старый вебхук и устанавливаем новый
    await bot.delete_webhook(drop_pending_updates=True)
    webhook_url = f"https://coocker-bot.onrender.com/webhook"
    await bot.set_webhook(url=webhook_url, allowed_updates=dp.resolve_used_update_types())
    print(f"Webhook set to {webhook_url}", flush=True)

# Инициализация при старте
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(init())