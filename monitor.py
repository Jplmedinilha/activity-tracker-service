import os
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from pynput import mouse, keyboard
from win10toast_click import ToastNotifier
from time import time as now
from pytz import timezone
from requests.auth import HTTPProxyAuth

load_dotenv()

WEBSERVICE_URL = os.getenv("WEBSERVICE_URL")
X_AUTH_HASH = os.getenv("X_AUTH_HASH")
SHORTCUTS = [s.strip().lower() for s in os.getenv("SHORTCUTS", "").split(",") if s.strip()]
KEYS = [k.strip().lower() for k in os.getenv("KEYS", "").split(",") if k.strip()]

HOSTNAME = os.getenv("HOSTNAME")

# Proxy config

proxy_host = os.getenv("PROXY_CONFIG_HTTP")
proxy_user = os.getenv("PROXY_USER")
proxy_pw = os.getenv("PROXY_PW")

proxies = None
auth = None

if proxy_host:
    proxies = {
        "http": f"http://{proxy_host}",
        "https": f"http://{proxy_host}"
    }

    if proxy_user and proxy_pw:
        auth = HTTPProxyAuth(proxy_user, proxy_pw)

CONTROL_CHAR_MAP = {
    '\x03': 'ctrl+c',  # Ctrl+C
    '\x16': 'ctrl+v',  # Ctrl+V
    '\x18': 'ctrl+x',  # Ctrl+X
    '\x06': 'ctrl+f',  # Ctrl+F
    '\x1a': 'ctrl+z',  # Ctrl+Z
    '\x19': 'ctrl+y',  # Ctrl+Y
    '\x01': 'ctrl+a',  # Ctrl+A
    '\x0e': 'ctrl+n',  # Ctrl+N
    '\x13': 'ctrl+s',  # Ctrl+S
    '\x0c': 'ctrl+l',  # Ctrl+L
    '\x0f': 'ctrl+o',  # Ctrl+O
}

hostname = HOSTNAME
toaster = ToastNotifier()
pressed_keys = set()
last_shortcut_time = {}

logging.basicConfig(filename="monitor_log.txt", level=logging.INFO, format="%(asctime)s | %(message)s")

custom_keys = set(SHORTCUTS + KEYS)
custom_counts_template = {key: 0 for key in custom_keys}

def reset_counts():
    return {
        "right_clicks": 0,
        "left_clicks": 0,
        "scroll_up": 0,
        "scroll_down": 0,
        "total_keys": 0,
        "custom_counts": custom_counts_template.copy()
    }

counts = reset_counts()

def get_active_window_title():
    try:
        import win32gui
        window = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(window)
    except:
        return ""

def on_click(x, y, button, pressed):
    if pressed:
        if button == mouse.Button.left:
            counts["left_clicks"] += 1
            if "left_clicks" in counts["custom_counts"]:
                counts["custom_counts"]["left_clicks"] += 1
            if "clicks" in counts["custom_counts"]:
                counts["custom_counts"]["clicks"] += 1
        elif button == mouse.Button.right:
            counts["right_clicks"] += 1
            if "right_clicks" in counts["custom_counts"]:
                counts["custom_counts"]["right_clicks"] += 1
            if "clicks" in counts["custom_counts"]:
                counts["custom_counts"]["clicks"] += 1

def on_scroll(x, y, dx, dy):
    if dy > 0:
        counts["scroll_up"] += 1
    elif dy < 0:
        counts["scroll_down"] += 1

def normalize_key(key):
    key_map = {
        'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
        'alt_l': 'alt', 'alt_r': 'alt',
        'shift_l': 'shift', 'shift_r': 'shift',
        'tab': 'tab',
        'enter': 'enter',
        'backspace': 'backspace',
        'print_screen': 'printscreen',
        'cmd': 'win'
    }
    return key_map.get(key, key)

def on_press(key):
    try:
        if hasattr(key, 'char') and key.char:
            k = key.char.lower()
            if k in CONTROL_CHAR_MAP:
                shortcut = CONTROL_CHAR_MAP[k]
                if shortcut in counts["custom_counts"]:
                    counts["custom_counts"][shortcut] += 1
                return
        else:
            k = str(key).replace("Key.", "").lower()
            k = normalize_key(k)
    except:
        return

    pressed_keys.add(k)
    counts["total_keys"] += 1

    for shortcut in SHORTCUTS:
        keys = shortcut.split("+")
        if keys[0] == "alt" and keys[1] == "tab" and "alt" in pressed_keys and k == "tab":
            now_time = now()
            if now_time - last_shortcut_time.get(shortcut, 0) > 0.3:
                counts["custom_counts"][shortcut] += 1
                last_shortcut_time[shortcut] = now_time
        elif all(mod in pressed_keys for mod in keys):
            now_time = now()
            if now_time - last_shortcut_time.get(shortcut, 0) > 1:
                counts["custom_counts"][shortcut] += 1
                last_shortcut_time[shortcut] = now_time


    if k in KEYS:
        counts["custom_counts"][k] += 1

def on_release(key):
    try:
        if hasattr(key, 'char') and key.char:
            k = key.char.lower()
        else:
            k = str(key).replace("Key.", "").lower()
            k = normalize_key(k)
    except:
        return

    pressed_keys.discard(k)

def send_data():
    global counts
    brasil = timezone("America/Sao_Paulo")
    timestamp = datetime.now(brasil).strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "timestamp": timestamp,
        "hostname": hostname,
        "window_title": get_active_window_title(),
        "right_clicks": counts["right_clicks"],
        "left_clicks": counts["left_clicks"],
        "scroll_up": counts["scroll_up"],
        "scroll_down": counts["scroll_down"],
        "total_keys": counts["total_keys"],
        "custom_counts": counts["custom_counts"]
    }

    headers = {"x-auth-hash": X_AUTH_HASH}

    try:
        response = requests.post(
            WEBSERVICE_URL,
            json=payload,
            headers=headers,
            timeout=10,
            verify=False,
            proxies=proxies,
            auth=auth
        )
        # print("HEADERS:", headers)
        # print("PAYLOAD:", payload)
        if response.status_code == 201:
            log_msg = f"{response.status_code} {response.reason} | Dados enviados com sucesso"
        else:
            msg = f"Falha ao enviar dados - {response.status_code} {response.reason}"
            log_msg = f"{response.status_code} {response.reason} | Erro ao enviar dados"
            print(f"[ERRO] {msg}")
            toaster.show_toast("Erro ao enviar dados", msg, duration=5, threaded=True, icon_path="icone.ico")
    except Exception as e:
        msg = f"Exceção: {e}"
        log_msg = f"EXCEPTION | {str(e)}"
        print(f"[EXCEPTION] {msg}")
        toaster.show_toast("Erro de conexão", msg, duration=5, threaded=True, icon_path="icone.ico")

    logging.info(log_msg)
    counts = reset_counts()

mouse.Listener(on_click=on_click, on_scroll=on_scroll).start()
keyboard.Listener(on_press=on_press, on_release=on_release).start()

while True:
    send_data()
    time.sleep(60)
