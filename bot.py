import os
import json
import datetime
import anthropic
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")

claude = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# Загружаем базу заведений
PLACES = []
try:
    with open("moscow_places_full.json", encoding="utf-8") as f:
        PLACES = json.load(f)
    print(f"База загружена: {len(PLACES)} заведений")
except Exception as e:
    print(f"База не найдена: {e}")

CATEGORY_KEYWORDS = {
    "Ресторан": ["ресторан", "ужин", "поесть", "кухня", "еда", "обед", "стейк", "суши", "пицца", "грузин", "итальян", "японск"],
    "Бар": ["бар", "коктейл", "выпить", "пиво", "вино", "бар-хоппинг", "паб", "напитк"],
    "Кофейня": ["кофе", "кофейня", "капучино", "десерт", "торт", "кондитер", "чай"],
    "Клуб": ["клуб", "танцевать", "вечеринк", "дискотек", "техно", "хаус", "рейв", "ночн"],
}

def get_moscow_time():
    tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(tz)
    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    return now, days[now.weekday()], now.strftime("%H:%M")

def detect_categories(text):
    text_lower = text.lower()
    cats = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            cats.append(cat)
    return cats if cats else ["Ресторан", "Бар", "Кофейня"]

def search_places(text, limit=15):
    if not PLACES:
        return []
    cats = detect_categories(text)
    filtered = [p for p in PLACES if p.get("category") in cats]
    filtered.sort(key=lambda x: (-(x.get("rating") or 0), -(x.get("reviews") or 0)))
    return filtered[:limit]

def format_places_for_prompt(places):
    if not places:
        return "База заведений недоступна."
    lines = []
    for p in places:
        line = f"- {p['name']} ({p.get('category','')})"
        if p.get("address"):
            line += f" | Адрес: {p['address']}"
        if p.get("rating"):
            line += f" | Рейтинг: {p['rating']}"
        if p.get("hours"):
            line += f" | Часы: {p['hours']}"
        lines.append(line)
    return "\n".join(lines)

SYSTEM_PROMPT = """Ты — Nightout. Личный консьерж по вечерам в Москве. Говоришь как умный друг — тепло, уверенно, с лёгкой иронией. Никогда не пишешь как справочник или робот.

СТИЛЬ ОТВЕТА:
- Текст живой и приятный для чтения — как будто друг рассказывает, а не перечисляет
- Не громоздко — каждое слово на своём месте
- Немного характера и настроения — но без пафоса
- Никакого markdown, звёздочек, решёток — только чистый текст

ПРАВИЛА:
- Используй ТОЛЬКО места из предоставленного списка. Никаких других заведений.
- Всегда указывай рейтинг и часы работы — это обязательно
- Если рейтинг или часы неизвестны — не упоминай их вовсе
- Адрес — только если он есть в данных
- Бары и алкоголь — только если пользователь сам об этом просит
- Количество мест — по смыслу запроса, не больше и не меньше

ФОРМАТ каждого места:
Название — одна живая фраза почему стоит идти
Адрес, рейтинг X.X, работает до XX:XX
(одна строка о переходе если есть следующая точка)"""

WELCOME = """Привет, {name}. Меня зовут Nightout.

Я знаю Москву лучше большинства москвичей — где поужинать так чтобы запомнилось, куда пойти после, как провести вечер без лишних раздумий.

Просто напиши что тебе нужно — остальное за мной."""

user_histories = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    name = update.effective_user.first_name
    await update.message.reply_text(WELCOME.format(name=name))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    text = update.message.text

    if user_id not in user_histories:
        user_histories[user_id] = []

    now, day_name, time_str = get_moscow_time()
    moscow_time = f"Сейчас в Москве: {day_name}, {time_str}"

    places = search_places(text)
    places_text = format_places_for_prompt(places)

    user_message = f"""{moscow_time}
Меня зовут {name}. Мой запрос: {text}

Доступные заведения из базы:
{places_text}

Составь сценарий используя только эти места. Начни с обращения по имени и одной живой фразы под настроение. Затем — ВЕЧЕР ГОТОВ и сам план. В конце — короткое тёплое напутствие."""

    user_histories[user_id].append({"role": "user", "content": user_message})

    if len(user_histories[user_id]) > 10:
        user_histories[user_id] = user_histories[user_id][-10:]

    try:
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=user_histories[user_id]
        )
        answer = response.content[0].text
        user_histories[user_id].append({"role": "assistant", "content": answer})
    except Exception as e:
        answer = "Что-то пошло не так. Попробуй ещё раз через минуту."
        print(f"Ошибка: {e}")

    await update.message.reply_text(answer)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Nightout бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
