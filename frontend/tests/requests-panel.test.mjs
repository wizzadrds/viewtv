import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import test from "node:test";

const base = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const panel = readFileSync(resolve(base, "components/requests-panel.tsx"), "utf8");
const app = readFileSync(resolve(base, "components/viewtv-app.tsx"), "utf8");

test("búsqueda manual y selección usan las rutas existentes de la API", () => {
  assert.match(panel, /apiRequest\("\/solicitudes", \{/);
  assert.match(panel, /method: "POST"/);
  assert.match(panel, /tipo_medio: kind/);
  assert.match(panel, /anio: Number\(year\)/);
  assert.match(panel, /"\/solicitudes\/" \+ selectedId \+ "\/resultados"/);
  assert.match(panel, /"\/solicitudes\/" \+ selectedId \+ "\/seleccion"/);
  assert.match(panel, /resultado_id: resultId/);
  assert.match(panel, /onSubmit=\{createRequest\}/);
  assert.match(panel, /onClick=\{\(\) => void chooseResult\(result.id\)\}/);
});

test("no busca ni selecciona automáticamente al montar la pantalla", () => {
  assert.match(panel, /useEffect\(\(\) => \{/);
  assert.match(panel, /loadRequests\(controller.signal\)/);
  assert.match(panel, /fetchResults\(\)/);
  const automaticEffects = panel.slice(
    panel.indexOf("  useEffect("),
    panel.indexOf("  async function createRequest("),
  );
  assert.doesNotMatch(automaticEffects, /createRequest\(/);
  assert.doesNotMatch(automaticEffects, /chooseResult\(/);
  assert.match(panel, /const REFRESH_MS = 10_000;/);
});

test("protege las sesiones y limpia temporizadores y peticiones", () => {
  assert.match(panel, /status === 401/);
  assert.match(panel, /onUnauthorized\(\)/);
  assert.match(panel, /controller.abort\(\)/);
  assert.match(panel, /clearInterval\(interval\)/);
  assert.match(panel, /removeEventListener\("visibilitychange", refreshVisible\)/);
  assert.match(panel, /requestId === lastRequest.current/);
  assert.match(panel, /requestId === latestResults.current/);
});

test("la navegación respeta la biblioteca, la reproducción y descargas", () => {
  assert.match(app, /import RequestsPanel from/);
  assert.match(app, /view === "requests"/);
  assert.match(app, />Buscar y pedir<\/button>/);
  assert.match(app, /onShowDownloads=\{\(\) => setView\("downloads"\)\}/);
  assert.match(app, /view === "downloads"/);
  assert.match(app, /view === "catalog"/);
  assert.match(app, /handlePlay/);
});

test("la selección explícita activa el flujo automático, sin reintentos de búsquedas fallidas", () => {
  assert.match(panel, /Al pulsar «Descargar», iniciará el proceso automáticamente/);
  assert.match(panel, /No se reintentará automáticamente/);
  assert.match(panel, /Solicitar búsqueda/);
  assert.match(panel, /Resultado seleccionado/);
});

test("reproducción usa HLS firmado cuando el MKV no admite Direct Play", () => {
  assert.match(app, /import Hls from "hls.js"/);
  assert.match(app, /item.modo === "hls"/);
  assert.match(app, /Hls.isSupported\(\)/);
  assert.match(app, /player.destroy\(\)/);
  assert.match(app, /src=\{playbackMode === "direct" \? playbackUrl : undefined\}/);
  assert.match(app, /\/hls\?token=/);
});

test("el reproductor HLS está conectado al video visible, no a una referencia nula", () => {
  assert.match(app, /const videoRef = useRef<HTMLVideoElement>\(null\)/);
  assert.match(app, /if \(!playbackUrl \|\| playbackMode !== "hls" \|\| !videoRef\.current\) return/);
  assert.match(app, /<video\s+ref=\{videoRef\}/);
  assert.match(app, /player\.attachMedia\(video\)/);
});
