import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const base = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const app = readFileSync(resolve(base, "components/viewtv-app.tsx"), "utf8");
const storage = readFileSync(resolve(base, "components/storage-panel.tsx"), "utf8");
const types = readFileSync(resolve(base, "lib/api.ts"), "utf8");

test("una película sigue en el catálogo, marcada por perfil sin ocultarse", () => {
  assert.match(types, /visto: boolean;/);
  assert.match(types, /perfil_id: number;/);
  assert.match(app, /item\.visto \? "Vista en este perfil"/);
  assert.match(app, /Tu colección sigue disponible en todos los perfiles/);
  assert.doesNotMatch(app, /items\.filter\(\(item\) => !item\.visto\)/);
});

test("al terminar un vídeo solo marca el perfil que reprodujo", () => {
  assert.match(app, /onEnded=\{\(\) => \{ void markMovieViewedAfterPlayback\(\); \}\}/);
  const start = app.indexOf("  async function markMovieViewedAfterPlayback()");
  const stop = app.indexOf("  async function openFromDiscover(", start);
  assert.ok(start > 0 && stop > start);
  const ended = app.slice(start, stop);
  assert.match(ended, /film\?\.tipo !== "pelicula"/);
  assert.match(ended, /visto: true, perfil_id_esperado: expectedProfileId/);
  assert.match(ended, /generation !== profileGeneration\.current/);
  assert.match(ended, /requestId !== playbackRequest\.current/);
  assert.match(ended, /setItems\(\(previous\)/);
  assert.doesNotMatch(ended, /\/retirada|method:\s*"DELETE"|\/delete|unlink\(/i);
});

test("consultas de catálogo y almacenamiento están vinculadas a la sesión", () => {
  assert.match(app, /perfil_id_esperado: String\(expectedProfileId\)/);
  assert.match(app, /playback-info\?perfil_id_esperado=\$\{expectedProfileId\}/);
  assert.match(app, /data\.perfil_id !== expectedProfileId/);
  assert.match(storage, /perfil_id_esperado=\$\{profileId\}/);
  assert.match(storage, /listing\.perfil_id !== profileId/);
  assert.match(app, /profileId=\{profile\.id\}/);
});

test("cambiar de perfil invalida vídeos y peticiones anteriores", () => {
  assert.match(app, /const profileGeneration = useRef\(0\)/);
  assert.match(app, /profileGeneration\.current \+= 1/);
  assert.match(app, /playbackRequest\.current \+= 1/);
  const start = app.indexOf("  async function handleLogout()");
  const stop = app.indexOf("  function closeDetails()", start);
  const logout = app.slice(start, stop);
  assert.match(logout, /setSelectedItem\(null\)/);
  assert.match(logout, /setPlaybackUrl\(null\)/);
  assert.match(logout, /setItems\(\[\]\)/);
});

test("solicitar retirada sigue siendo independiente de marcar vista", () => {
  assert.match(storage, /JSON\.stringify\(\{ titulo: typed, perfil_id_esperado: profileId \}\)/);
  assert.match(storage, /visto: !film\.visto, perfil_id_esperado: profileId/);
  assert.match(storage, /La marca «vista» pertenece únicamente a este perfil/);
  assert.match(storage, /La retirada requiere revisión y autorización separada/);
});
