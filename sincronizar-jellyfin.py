import getpass
import json
import urllib.request
import urllib.error
import http.cookiejar

base = "http://127.0.0.1:8000"
nombre = input("Perfil VIEWTV: ").strip()
pin = getpass.getpass("PIN (no se mostrará): ")

cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cookies)
)

login = urllib.request.Request(
    base + "/auth/login",
    data=json.dumps({"nombre": nombre, "pin": pin}).encode(),
    headers={"Content-Type": "application/json"},
)

try:
    with opener.open(login, timeout=10) as r:
        print("Autenticación:", r.status)

    pin = None

    req = urllib.request.Request(
        base + "/jellyfin/catalog/sync",
        data=b"",
        method="POST",
    )

    with opener.open(req, timeout=60) as r:
        print("Sincronización:", r.status)
        print(json.dumps(json.load(r), indent=2, ensure_ascii=False))

except urllib.error.HTTPError as e:
    print("Error HTTP:", e.code)
    print(e.read().decode()[:300])
except Exception as e:
    print("Error:", type(e).__name__, str(e))

