import os
import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

# Временная заглушка Redis (чтобы не падало)
class FakeRedis:
    async def get(self, *args, **kwargs): return None
    async def setex(self, *args, **kwargs): return True
    async def delete(self, *args, **kwargs): return True
    async def exists(self, *args, **kwargs): return 0
    async def incr(self, *args, **kwargs): return 1
    async def expire(self, *args, **kwargs): return True

redis_client = FakeRedis()
# Если настроите настоящий Redis, замените на:
# redis_client = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

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

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Антиспам-бот работает. Добавьте меня в группу с правами администратора.")

@dp.message()
async def anti_spam_handler(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    if has_forbidden_link(message.text) or has_spam_words(message.text):
        await message.delete()
        await message.answer("🚫 Спам запрещён!")

async def main():
    print("Бот запущен и работает через long polling", flush=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())