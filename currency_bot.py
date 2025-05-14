from dotenv import load_dotenv
import os
import logging
import requests
import sys
import asyncio
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# Загрузка переменных окружения
load_dotenv()

API_KEY = os.getenv("EXCHANGE_API_KEY")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

BASE_URL = "https://api.apilayer.com/exchangerates_data/latest"
CONVERT_URL = "https://api.apilayer.com/exchangerates_data/convert"
CURRENCIES = ['USD', 'EUR', 'THB', 'VND', 'RUB', 'LKR', 'CNY', 'JPY', 'GBP', 'INR']

logging.basicConfig(level=logging.INFO)
user_base_currency = {}

def get_rates(base='EUR', symbols=None):
    if symbols is None:
        symbols = ','.join(CURRENCIES)
    url = f"{BASE_URL}?symbols={symbols}&base={base}"
    headers = {"apikey": API_KEY}
    response = requests.get(url, headers=headers)
    try:
        return response.json()
    except Exception as e:
        print("Ошибка при парсинге ответа API:", e)
        return None

def convert_currency(amount, from_currency, to_currency):
    url = f"{CONVERT_URL}?from={from_currency}&to={to_currency}&amount={amount}"
    headers = {"apikey": API_KEY}
    response = requests.get(url, headers=headers)
    try:
        data = response.json()
        return data.get('result')
    except Exception as e:
        print("Ошибка при конвертации:", e)
        return None

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Курсы валют", callback_data="show_rates")],
        [InlineKeyboardButton("🌐 Сменить валюту", callback_data="change_base")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(code, callback_data=f"setbase_{code}")]
        for code in CURRENCIES
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("Выберите базовую валюту:", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text("Выберите базовую валюту:", reply_markup=reply_markup)

async def rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    base = user_base_currency.get(user_id, 'EUR')
    data = get_rates(base=base)

    if data and 'rates' in data:
        reply = f"Курсы валют относительно {base}:\n"
        for currency in CURRENCIES:
            if currency != base and currency in data['rates']:
                reply += f"{currency}: {data['rates'][currency]:.2f}\n"
        reply += "\n💱 Чтобы выполнить конвертацию, введите, например: `10 USD to RUB`"
        await update.message.reply_text(reply, reply_markup=main_menu())
    else:
        await update.message.reply_text("Ошибка при получении курсов валют.", reply_markup=main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("setbase_"):
        base = data.split("_")[1]
        user_base_currency[user_id] = base
        await query.edit_message_text(f"Базовая валюта установлена: {base}", reply_markup=main_menu())
    elif data == "show_rates":
        base = user_base_currency.get(user_id, 'EUR')
        data = get_rates(base=base)
        if data and 'rates' in data:
            reply = f"Курсы валют относительно {base}:\n"
            for currency in CURRENCIES:
                if currency != base and currency in data['rates']:
                    reply += f"{currency}: {data['rates'][currency]:.2f}\n"
            reply += "\n💱 Чтобы выполнить конвертацию, введите, например: `10 USD to RUB`"
            await query.edit_message_text(reply, reply_markup=main_menu())
        else:
            await query.edit_message_text("Ошибка при получении курсов валют.", reply_markup=main_menu())
    elif data == "change_base":
        await start(update, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    match = re.match(r"(\d+(?:\.\d+)?)\s*([A-Z]{3})\s+to\s+([A-Z]{3})", msg, re.IGNORECASE)
    if match:
        amount = float(match.group(1))
        from_cur = match.group(2).upper()
        to_cur = match.group(3).upper()
        result = convert_currency(amount, from_cur, to_cur)
        if result is not None:
            await update.message.reply_text(f"{amount:.2f} {from_cur} = {result:.2f} {to_cur}", reply_markup=main_menu())
        else:
            await update.message.reply_text("Ошибка при конвертации.", reply_markup=main_menu())
    else:
        await update.message.reply_text("Неверный формат. Пример: `10 USD to RUB`", reply_markup=main_menu())

def main():
    if sys.platform.startswith('win') and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rates", rates))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()

if __name__ == "__main__":
    main()
