import asyncio
import os
from aiogram import Bot, Dispatcher, types
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message()
async def echo(message: types.Message):
    await message.answer(f"Echo: {message.text}")

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot alive"

@app.route('/webhook', methods=['POST'])
async def webhook():
    json_data = request.get_json()  # ← НЕТ await
    update = types.Update.model_validate(json_data, context={"bot": bot})
    # Запускаем обработку в фоне, не дожидаясь результата
    asyncio.create_task(dp.feed_update(bot, update))
    return "ok", 200

async def setup():
    await bot.delete_webhook()
    await bot.set_webhook("https://coocker-bot.onrender.com/webhook")
    print("Webhook set")

asyncio.run(setup())