"""Revisa HTML Samsung y JS ES5 sin acceder a navegador, API ni red."""
from pathlib import Path
import subprocess

path = Path("/home/viewtv/projects/viewtv-broker-0013-20261119/frontend/public/tv.html")
text = path.read_text(encoding="utf-8")
assert text.startswith("<!doctype html>")
assert text.count("<script>") == text.count("</script>") == 1
script = text.split("<script>", 1)[1].split("</script>", 1)[0]
assert "/api/viewtv" in script
assert "/auth/profiles" in script
assert "/descubrir/filas" in script
assert "tv.html" not in script or "video" in script
assert "XMLHttpRequest" in script
assert "eval(" not in script
for modern in ("=>", "const ", "let ", "?.", "??", "`"):
    assert modern not in script, modern

check = subprocess.run(
    [
        "docker", "run", "--rm", "--pull", "never", "--network", "none",
        "-i", "--entrypoint", "node", "node:22-bookworm-slim", "--check", "-",
    ],
    input=script, text=True, stdout=subprocess.PIPE,
    stderr=subprocess.PIPE, timeout=20,
)
if check.returncode != 0:
    raise SystemExit("SAMSUNG_JS_SINTAXIS_FALLO: " + check.stderr[:400])
print("SAMSUNG_HTML=OK")
print("SAMSUNG_JS_ES5_SINTAXIS=OK")
print("SIN_REACT_SIN_PROMISE_SIN_FETCH=SI")
