import os
import json
import threading
import anthropic
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
claude = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

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
- Учитывай время СТРОГО. Если сейчас позднее время и заведение закрывается — НЕ предлагай его. Только места которые открыты сейчас и проработают ещё минимум час."""

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
                result = json.dumps({
                    "temp": temp,
                    "desc": desc,
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
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    from bot import main
    main()
