import requests
TOKEN = "ваш_токен"  # вставьте
url = f"https://api.telegram.org/bot{8274497752:AAEuv2hHb7dxudbbRCcOezNQdiOJCwE3g7g}/getMe"
try:
    r = requests.get(url, timeout=10)
    print(r.status_code, r.json())
except Exception as e:
    print("Ошибка:", e)