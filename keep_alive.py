from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "Bot Discord của Kirosa đang chạy phà phà 24/7!"

def run():
    # Lấy Port của Render cấp, nếu không có thì dùng mặc định 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()