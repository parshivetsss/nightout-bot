import os
import anthropic
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")

claude = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

SYSTEM_PROMPT = """Ты — Nightout. Личный консьерж по вечерам в Москве. Говоришь тепло, уверенно, без пафоса. Как умный друг который всегда знает куда пойти.

ПРАВИЛА ТОЧНОСТИ — это самое важное:
- Называй ТОЛЬКО те места в которых ты абсолютно уверен. Если есть хоть малейшее сомнение — не называй вообще.
- Адрес указывай только если уверен на 100%. Если не уверен — только название и метро.
- Рейтинг указывай только если знаешь реальную цифру.
- Средний чек только если знаешь реальную цифру.
- Популярные блюда и напитки — только реальные позиции из меню.
- Никогда не придумывай детали. Лучше меньше но точно.
- Никакого markdown, звёздочек, решёток — только чистый текст.
- Бары и алкоголь только если пользователь явно просит.
- Вечер не обязан заканчиваться баром."""

WELCOME = """Привет, {name}. Меня зовут Nightout.

Я знаю Москву лучше большинства москвичей — где поужинать так чтобы запомнилось, куда пойти после, как провести вечер без лишних раздумий.

Просто напиши что тебе нужно — остальное за мной."""

USER_PROMPT = """Меня зовут {name}. Мой запрос: {text}

Ответь как личный консьерж. Начни с обращения по имени и 1-2 предложений под настроение запроса.

Затем напиши ВЕЧЕР ГОТОВ и составь сценарий.

Количество мест определяй сам по запросу:
- Просит один ресторан — одно место
- Хочет вечер — две-три точки
- Бар-хоппинг или клубная ночь — три-пять точек
- Не добавляй лишние точки ради количества

Для каждого места строго в таком порядке — только если уверен в данных:
Название
Адрес и метро (только если уверен на 100%)
Рейтинг: X.X (только если знаешь реальную цифру)
Средний чек: X рублей на человека (только если знаешь)
Что попробовать: (только реальные позиции из меню)
Одна живая фраза почему именно здесь

Между точками — как добраться и сколько идти.

В конце — итоговый бюджет и одна короткая тёплая фраза напутствие.

Если спрашивают о месте которое не знаешь — честно скажи и предложи альтернативу."""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(WELCOME.format(name=name))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    text = update.message.text

    await update.message.reply_text("Составляю вечер...")

    try:
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": USER_PROMPT.format(name=name, text=text)
            }]
        )
        answer = response.content[0].text
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
