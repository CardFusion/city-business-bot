import asyncio
import json
import time
import os
import random

from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

DATA_FILE = "players.json"

INCOME_INTERVAL = 30
OFFLINE_MULTIPLIER = 0.1

AD_PRICE = 100
AD_BONUS = 1.2
AD_DURATION = 1200

EVENT_CHANCE = 0.15

START_INCOME = 0.5


BUSINESSES = {
    1: {"name": "🍔 Фастфуд", "price": 300, "income": 1},
    2: {"name": "🏪 Магазин", "price": 1200, "income": 3},
    3: {"name": "🏬 Торговый центр", "price": 6000, "income": 10},
    4: {"name": "🏭 Завод", "price": 30000, "income": 35},
}

WORKERS = {
    1: {"name": "👨‍🍳 Бариста", "price": 300, "income": 0.5},
    2: {"name": "👔 Менеджер", "price": 2000, "income": 3},
}


# ===============================
# БАЗА
# ===============================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}

    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


# ===============================
# УДАЛЕНИЕ СООБЩЕНИЙ
# ===============================

async def clear(update, context):

    try:
        await update.message.delete()
    except:
        pass

    if "last_bot_msg" in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data["last_bot_msg"]
            )
        except:
            pass


async def send(update, context, text):

    msg = await update.effective_chat.send_message(text)

    context.user_data["last_bot_msg"] = msg.message_id


# ===============================
# ДОХОД
# ===============================

def calculate_income(player):

    now = time.time()

    passed = now - player["last_collect"]

    cycles = int(passed // INCOME_INTERVAL)

    if cycles <= 0:
        return

    income = player["income"]

    if player["ads_until"] > now:
        income *= AD_BONUS

    if now - player["last_online"] > 300:
        income *= OFFLINE_MULTIPLIER

    income *= 1 + (player["level"] * 0.1)

    total = cycles * income

    player["balance"] += round(total, 2)

    player["last_collect"] = now
    player["last_online"] = now


# ===============================
# RANDOM EVENT
# ===============================

def random_event(player):

    if random.random() > EVENT_CHANCE:
        return None

    events = [

        ("🎉 Городской фестиваль", "Доход увеличен на 30% на 10 минут", "boost"),

        ("💼 Инвестор", "+200$", "money"),

        ("🔥 Пожар", "-10% денег", "loss"),

        ("🏛 Государственный грант", "+500$", "money"),
    ]

    e = random.choice(events)

    if e[2] == "money":
        player["balance"] += 200

    if e[2] == "loss":
        player["balance"] *= 0.9

    if e[2] == "boost":
        player["ads_until"] = time.time() + 600

    return f"""
⚡ Случайное событие!

{e[0]}

{e[1]}
"""


# ===============================
# DAILY
# ===============================

def daily_reward(day):

    return min(10 * (day // 2 + 1), 1000)


# ===============================
# /start
# ===============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await clear(update, context)

    data = load_data()

    user_id = str(update.effective_user.id)

    if user_id not in data:

        data[user_id] = {

            "name": update.effective_user.first_name,

            "balance": 5,

            "income": START_INCOME,

            "bank": 0,

            "level": 0,

            "workers": {},

            "business": {"coffee": 1},

            "ads_until": 0,

            "last_collect": time.time(),

            "last_online": time.time(),

            "last_daily": 0,

            "daily_day": 1
        }

        save_data(data)

        text = f"""
🏙 Добро пожаловать в City Owner!

Ты начинаешь путь предпринимателя.

☕ Первый бизнес:
Кофейня

Доход:
0.5$ / 30 сек

Используй команды через меню Telegram.
"""

    else:

        text = "🏙 С возвращением!\n\nИспользуй /city"

    await send(update, context, text)


# ===============================
# /city
# ===============================

async def city(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await clear(update, context)

    data = load_data()

    user_id = str(update.effective_user.id)

    player = data[user_id]

    calculate_income(player)

    event = random_event(player)

    save_data(data)

    text = f"""
🏙 Твой город

💰 Баланс: {round(player['balance'],2)}$

📈 Доход: {round(player['income'],2)} / 30 сек

🏗 Уровень города: {player['level']}

"""

    for bid, count in player["business"].items():

        if bid == "coffee":
            text += f"\n☕ Кофейня × {count}"
            continue

        b = BUSINESSES[int(bid)]

        text += f"\n{b['name']} × {count}"

    if event:
        text += f"\n\n{event}"

    await send(update, context, text)


# ===============================
# BUSINESS
# ===============================

async def business(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await clear(update, context)

    text = "🏢 Бизнесы\n"

    for i, b in BUSINESSES.items():

        text += f"""

{i}. {b['name']}
Цена: {b['price']}$
Доход: {b['income']}$
"""

    text += "\nКупить: /buy ID"

    await send(update, context, text)


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await clear(update, context)

    if not context.args:
        await send(update, context, "Используй /buy ID")
        return

    data = load_data()

    user_id = str(update.effective_user.id)

    player = data[user_id]

    calculate_income(player)

    bid = int(context.args[0])

    if bid not in BUSINESSES:
        await send(update, context, "❌ Бизнес не найден")
        return

    b = BUSINESSES[bid]

    if player["balance"] < b["price"]:
        await send(update, context, "❌ Недостаточно денег")
        return

    player["balance"] -= b["price"]

    player["income"] += b["income"]

    player["business"][str(bid)] = player["business"].get(str(bid), 0) + 1

    save_data(data)

    await send(update, context, f"🏢 Куплен бизнес\n\n{b['name']}")


# ===============================
# BANK
# ===============================

async def bank(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await clear(update, context)

    data = load_data()

    player = data[str(update.effective_user.id)]

    text = f"""
🏦 Банк

Баланс банка:
{round(player['bank'],2)}$

Команды:

/deposit сумма
/withdraw сумма
"""

    await send(update, context, text)


async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await clear(update, context)

    if not context.args:
        return

    amount = float(context.args[0])

    data = load_data()

    player = data[str(update.effective_user.id)]

    if player["balance"] < amount:
        await send(update, context, "❌ Недостаточно денег")
        return

    player["balance"] -= amount

    player["bank"] += amount

    save_data(data)

    await send(update, context, "💰 Деньги положены в банк")


async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await clear(update, context)

    if not context.args:
        return

    amount = float(context.args[0])

    data = load_data()

    player = data[str(update.effective_user.id)]

    if player["bank"] < amount:
        await send(update, context, "❌ Недостаточно денег в банке")
        return

    player["bank"] -= amount

    player["balance"] += amount

    save_data(data)

    await send(update, context, "💰 Деньги сняты")


# ===============================
# DAILY
# ===============================

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await clear(update, context)

    data = load_data()

    player = data[str(update.effective_user.id)]

    now = time.time()

    if now - player["last_daily"] < 86400:

        await send(update, context, "⏳ Приходи завтра")
        return

    reward = daily_reward(player["daily_day"])

    player["balance"] += reward

    player["daily_day"] += 1

    player["last_daily"] = now

    save_data(data)

    await send(update, context, f"🎁 Награда: {reward}$")


# ===============================
# TOP
# ===============================

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await clear(update, context)

    data = load_data()

    players = list(data.values())

    players.sort(key=lambda x: x["balance"], reverse=True)

    text = "🏆 Топ игроков\n\n"

    medals = ["🥇","🥈","🥉"]

    for i,p in enumerate(players[:10]):

        medal = medals[i] if i < 3 else f"{i+1}."

        text += f"{medal} {p['name']} — {round(p['balance'],2)}$\n"

    await send(update, context, text)


# ===============================
# COMMAND MENU
# ===============================

async def set_commands(app):

    commands = [

        BotCommand("city","Город"),
        BotCommand("business","Бизнесы"),
        BotCommand("buy","Купить бизнес"),
        BotCommand("bank","Банк"),
        BotCommand("daily","Ежедневная награда"),
        BotCommand("top","Топ игроков"),
    ]

    await app.bot.set_my_commands(commands)


# ===============================
# MAIN
# ===============================

async def post_init(app):
    await set_commands(app)


def main():

    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("city", city))
    app.add_handler(CommandHandler("business", business))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("bank", bank))
    app.add_handler(CommandHandler("deposit", deposit))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("top", top))

    print("Бот запущен")

    app.run_polling()


if __name__ == "__main__":
    main()