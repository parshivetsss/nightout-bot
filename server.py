import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/app":
            self.path = "/nightout_app.html"
        return super().do_GET()

    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Веб-сервер запущен на порту {port}")
    server.serve_forever()

if __name__ == "__main__":
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    from bot import main
    main()
