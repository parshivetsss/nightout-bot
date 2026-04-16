import os
import anthropic
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")

claude = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

SYSTEM_PROMPT = """Ты — Nightout. Личный консьерж по вечерам в Москве. Говоришь тепло, уверенно, без пафоса. Как умный друг который всегда знает куда пойти. Никакого markdown, звёздочек, решёток — только чистый текст.

ПРАВИЛА ТОЧНОСТИ:
- Называй ТОЛЬКО те места в которых абсолютно уверен. Если есть сомнение — не называй.
- Адрес только если уверен на 100%. Если не уверен — только название и метро.
- Рейтинг только если знаешь реальную цифру.
- Средний чек только если знаешь реальную цифру.
- Популярные блюда — только реальные позиции из меню.
- Никогда не придумывай детали. Лучше меньше но точно.
- Бары и алкоголь только если пользователь явно просит.
- Вечер не обязан заканчиваться баром.

ПРАВИЛА УТОЧНЕНИЙ:
- Если в запросе нет района или части города — спроси откуда стартует или в каком районе хочет провести вечер.
- Если нет дня и времени — спроси когда планирует выйти.
- Если запрос совсем размытый и непонятно формат — задай один уточняющий вопрос.
- Задавай максимум 2 уточняющих вопроса за раз, не больше.
- Если район, время и формат понятны — сразу составляй сценарий без лишних вопросов.
- Учитывай день недели при выборе мест — клубы работают в основном пт-сб, многие рестораны не принимают без брони в выходные вечером.

ФОРМАТ ОТВЕТА когда все данные есть:
Обращение по имени и 1-2 живых предложения под настроение.

ВЕЧЕР ГОТОВ

Для каждого места:
Название
Адрес и метро (только если уверен)
Рейтинг: X.X (только если знаешь)
Средний чек: X рублей на человека (только если знаешь)
Что попробовать: (только реальные позиции)
Одна живая фраза почему именно здесь

Между точками — переход: как добраться и сколько идти.

В конце — итоговый бюджет и одна короткая тёплая фраза напутствие."""

WELCOME = """Привет, {name}. Меня зовут Nightout.

Я знаю Москву лучше большинства москвичей — где поужинать так чтобы запомнилось, куда пойти после, как провести вечер без лишних раздумий.

Просто напиши что тебе нужно — остальное за мной."""

# Хранение истории диалогов
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

    user_histories[user_id].append({
        "role": "user",
        "content": f"Меня зовут {name}. {text}"
    })

    if len(user_histories[user_id]) > 10:
        user_histories[user_id] = user_histories[user_id][-10:]


    try:
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=user_histories[user_id]
        )
        answer = response.content[0].text

        user_histories[user_id].append({
            "role": "assistant",
            "content": answer
        })

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
