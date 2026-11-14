import getpass
import json
import urllib.request
import urllib.error
import http.cookiejar

base = "http://127.0.0.1:8000"

nombre = input("Nombre exacto del perfil VIEWTV: ").strip()
pin = getpass.getpass("PIN (no se mostrará): ")

cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cookies)
)

datos = json.dumps({"nombre": nombre, "pin": pin}).encode()
peticion = urllib.request.Request(
    base + "/auth/login",
    data=datos,
    headers={"Content-Type": "application/json"},
)

try:
    with opener.open(peticion, timeout=10) as respuesta:
        resultado = json.load(respuesta)
        print("Inicio de sesión:", respuesta.status, resultado.get("estado"))

    pin = None

    with opener.open(base + "/jellyfin/status", timeout=10) as respuesta:
        print("Estado Jellyfin:", respuesta.status)
        print(json.dumps(json.load(respuesta), indent=2, ensure_ascii=False))

except urllib.error.HTTPError as error:
    print("Error HTTP:", error.code)
    print(error.read().decode()[:300])
except Exception as error:
    print("Error:", type(error).__name__, str(error))
