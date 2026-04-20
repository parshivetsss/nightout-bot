import os
import json
import threading
import anthropic
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
claude = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# Хранилище планов для шаринга — ключ: короткий ID, значение: данные плана
SHARED_PLANS = {}

SYSTEM_PROMPT = """Ты — Nightout. Личный консьерж по вечерам в Москве. Говоришь тепло, уверенно, с лёгкой иронией. Никогда не пишешь как справочник.

Грамотность — абсолютный приоритет. Никаких орфографических ошибок.

Отвечай ТОЛЬКО в формате JSON. Никакого другого текста. Формат:
{
  "intro": "одно живое предложение — настрой на вечер, обращение по имени",
  "places": [
    {
      "num": 1,
      "name": "Название",
      "address": "Улица, дом · м. Метро",
      "rating": "4.8",
      "hours": "до 00:00",
      "category": "Ресторан",
      "desc": "одна живая фраза почему стоит идти",
      "transition": "7 минут пешком до следующей точки"
    }
  ],
  "outro": "короткая тёплая фраза напутствие"
}

Правила:
- ТОЛЬКО реально существующие заведения Москвы которые ты точно знаешь. Никогда не придумывай названия.
- Если не уверен в названии или адресе — НЕ включай это место. Лучше меньше мест но все реальные.
- Адрес только если знаешь точно, иначе только метро
- Рейтинг только если знаешь реальную цифру, иначе пустая строка
- Часы только если знаешь точно, иначе пустая строка
- transition для последней точки — пустая строка
- Количество мест: свидание и прогулка — 2-3, друзья и культура — 3, клуб — 2-3, день рождения — 3
- Бары и алкоголь только если формат клуб или друзья
- Учитывай сезон и день недели
- Учитывай время СТРОГО. Только места которые точно открыты прямо сейчас и проработают ещё минимум час.
- Если не знаешь часы работы места — НЕ включай его в план совсем.
- Если сейчас после 23:00 или раннее утро — честно предупреди что выбор ограничен. Предлагай только круглосуточные или ночные заведения.
- Если подходящих мест нет — верни plan с пустым массивом places и объясни в поле intro: когда лучше планировать вечер."""

import datetime

def get_context():
    tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(tz)
    days = ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]
    month = now.month
    if month in [12,1,2]: season = "зима"
    elif month in [3,4,5]: season = "весна"
    elif month in [6,7,8]: season = "лето"
    else: season = "осень"
    return f"{days[now.weekday()]}, {now.strftime('%H:%M')}, {season}"

class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/", "/app"]:
            try:
                with open("nightout_app.html", "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
            except:
                self.send_response(404)
                self.end_headers()
        elif parsed.path.startswith("/plan/"):
            plan_id = parsed.path.replace("/plan/", "")
            plan = SHARED_PLANS.get(plan_id)
            if plan:
                # Отдаём HTML страницу которая показывает план и кнопку открыть в Telegram
                places = plan.get("places", "")
                fmt = plan.get("fmt", "Вечер")
                html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta property="og:title" content="Nightout — {fmt}">
<meta property="og:description" content="{places}">
<title>Nightout — {fmt}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#07070F;color:#EEEEF8;font-family:system-ui;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px}}
.logo{{font-size:20px;letter-spacing:6px;margin-bottom:24px;color:#C9AA71}}
.card{{background:#0C0C18;border:1px solid #181828;border-radius:16px;padding:20px;max-width:340px;width:100%;margin-bottom:20px}}
.fmt{{font-size:14px;color:#C9AA71;margin-bottom:12px}}
.place{{font-size:13px;color:#7878A0;margin:6px 0;line-height:1.5}}
.btn{{display:block;background:#C9AA71;color:#07070F;text-decoration:none;padding:14px 24px;border-radius:14px;font-size:14px;font-weight:500;text-align:center;max-width:340px;width:100%}}
.btn:active{{opacity:.9}}
.sub{{font-size:11px;color:#333350;margin-top:16px;text-align:center}}
</style></head><body>
<div class="logo">NIGHTOUT</div>
<div class="card">
<div class="fmt">{fmt}</div>
{"".join(f'<div class="place">· {p.strip()}</div>' for p in places.split("→"))}
</div>
<a class="btn" href="https://t.me/N1GHTOUT_bot/NIGHTOUT">Открыть в Telegram</a>
<div class="sub">Создай свой вечер в Nightout</div>
</body></html>"""
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode())
            else:
                self.send_response(302)
                self.send_header("Location", "https://t.me/N1GHTOUT_bot/NIGHTOUT")
                self.end_headers()
        elif parsed.path == "/api/weather":
            try:
                import urllib.request as ur
                req = ur.Request(
                    "https://wttr.in/Moscow?format=j1",
                    headers={"User-Agent": "curl/7.68.0"}
                )
                with ur.urlopen(req, timeout=5) as r:
                    data = json.loads(r.read())
                c = data["current_condition"][0]
                temp = c["temp_C"]
                desc = c["weatherDesc"][0]["value"]
                is_rain = any(w in desc.lower() for w in ["rain","drizzle","shower","snow","thunder","sleet"])
                is_cold = int(temp) < 5
                is_hot = int(temp) > 25
                emoji = "🌧" if is_rain else ("❄️" if is_cold else ("☀️" if is_hot else "🌤"))
                WEATHER_RU = {
                    "sunny": "солнечно", "clear": "ясно", "partly cloudy": "переменная облачность",
                    "cloudy": "облачно", "overcast": "пасмурно", "mist": "туман", "fog": "туман",
                    "light rain": "лёгкий дождь", "moderate rain": "дождь", "heavy rain": "сильный дождь",
                    "light drizzle": "морось", "drizzle": "морось", "freezing drizzle": "ледяная морось",
                    "light snow": "лёгкий снег", "moderate snow": "снег", "heavy snow": "сильный снег",
                    "blizzard": "метель", "thundery outbreaks possible": "гроза возможна",
                    "patchy rain possible": "местами дождь", "patchy snow possible": "местами снег",
                    "light sleet": "мокрый снег", "blowing snow": "поземок",
                    "freezing fog": "ледяной туман", "patchy light rain": "небольшой дождь",
                    "light rain shower": "ливень", "torrential rain shower": "ливень",
                    "patchy light drizzle": "морось", "freezing drizzle": "ледяная морось",
                    "patchy light snow": "небольшой снег", "light snow showers": "снегопад",
                    "thunder": "гроза", "thunderstorm": "гроза",
                }
                desc_lower = desc.lower()
                desc_ru = next((v for k, v in WEATHER_RU.items() if k in desc_lower), desc)
                result = json.dumps({
                    "temp": temp,
                    "desc": desc_ru,
                    "emoji": emoji,
                    "is_rain": is_rain,
                    "is_cold": is_cold,
                    "is_hot": is_hot
                }, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(result)
            except Exception as e:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"temp":"?","desc":"","emoji":"🌤","is_rain":False}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/plan":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))

                fmt = body.get("format", "вечер")
                district = body.get("district", "центр")
                name = body.get("name", "друг")
                extra = body.get("extra", "")

                ctx = get_context()

                user_msg = f"""Сейчас в Москве: {ctx}
Имя пользователя: {name}
Формат вечера: {fmt}
Район: {district}
{f'Дополнительно: {extra}' if extra else ''}

Составь сценарий вечера в формате JSON."""

                response = claude.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=1500,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_msg}]
                )

                text = response.content[0].text.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                data = json.loads(text)

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

            except Exception as e:
                print(f"Ошибка API: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        elif self.path == "/api/save":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                import random, string
                plan_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
                SHARED_PLANS[plan_id] = body
                result = json.dumps({"id": plan_id}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(result)
            except Exception as e:
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
        elif self.path == "/api/load":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                plan_id = body.get("id", "")
                plan = SHARED_PLANS.get(plan_id)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(plan or {}, ensure_ascii=False).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Сервер запущен на порту {port}")
    server.serve_forever()

if __name__ == "__main__":
    import time as _time

    # Запускаем веб-сервер
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # Ждём 5 секунд чтобы старый процесс точно завершился
    print("Ждём завершения старого процесса...")
    _time.sleep(5)

    # Запускаем бота
    from bot import main
    main()
