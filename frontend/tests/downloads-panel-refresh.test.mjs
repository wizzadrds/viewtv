// Pruebas de contrato estático para el refresco de descargas.
// La compilación de Next.js y la prueba de humo cubren ejecución/arranque.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import test from "node:test";

const directory = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(directory, "../components/downloads-panel.tsx"), "utf8");

test("descargas se consultan automáticamente cada 15 segundos", () => {
  assert.match(source, /const REFRESH_MS = 15_000;/);
  assert.match(source, /window\.setInterval\(refreshWhenVisible, REFRESH_MS\)/);
  assert.match(source, /document\.visibilityState === "visible"/);
  assert.match(source, /window\.clearInterval\(intervalId\)/);
});

test("al volver a la pestaña se refresca inmediatamente", () => {
  assert.match(source, /document\.addEventListener\("visibilitychange", refreshWhenVisible\)/);
  assert.match(source, /document\.removeEventListener\("visibilitychange", refreshWhenVisible\)/);
});

test("sin botón de actualización manual y sin estado extra", () => {
  assert.doesNotMatch(source, /↻ Actualizar|setRefreshIndex|onClick=\{handleRefresh\}/);
  assert.match(source, /Se actualiza automáticamente/);
  assert.match(source, /\/solicitudes\/descargas\?limit=\$\{PAGE_SIZE\}&offset=\$\{offset\}/);
});

test("se conservan errores, cancelación y paginación", () => {
  assert.match(source, /controller\.abort\(\)/);
  assert.match(source, /requestId === latestRequest/);
  assert.match(source, /status\?: number/);
  assert.match(source, /nextAvailable/);
  assert.match(source, /Anteriores/);
  assert.match(source, /Siguientes/);
});
