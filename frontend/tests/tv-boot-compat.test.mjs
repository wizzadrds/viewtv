import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const layout = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
const match = layout.match(/const bootGuard = `([\s\S]*?)`;/);
assert.ok(match, "Existe un guardián sin dependencia de React");
const script = match[1];

function simulate(hasBoot = true) {
  const events = {};
  const timers = [];
  const calls = [];
  const createElement = (tag) => ({
    tag,
    children: [],
    style: {},
    setAttribute() {},
    appendChild(child) { this.children.push(child); },
    textContent: "",
  });
  const body = createElement("body");
  const document = {
    body,
    querySelector(selector) {
      assert.equal(selector, ".boot-screen");
      return hasBoot ? {} : null;
    },
    createElement,
  };
  const window = {
    addEventListener(name, handler) { events[name] = handler; },
    setTimeout(handler, delay) { timers.push({ handler, delay }); },
  };
  class XMLHttpRequest {
    open(method, url) { calls.push({ method, url }); }
    send() {
      this.readyState = 4;
      this.status = 401;
      this.onreadystatechange();
    }
  }
  vm.runInNewContext(script, { window, document, XMLHttpRequest });
  return { window, events, timers, body, calls };
}

test("Tizen 5.0: código de arranque anterior a ES2018 y objetivo Chromium 63", () => {
  assert.ok(packageJson.browserslist.includes("chrome 63"));
  assert.doesNotMatch(script, /=>|\?\.|\?\?|\bconst\b|\blet\b/);
  assert.ok(layout.includes("dangerouslySetInnerHTML"));
});

test("AbortController de respaldo notifica aborto sin depender del navegador", () => {
  const { window } = simulate();
  const controller = new window.AbortController();
  let triggered = 0;
  controller.signal.addEventListener("abort", () => { triggered += 1; });
  controller.abort();
  controller.abort();
  assert.equal(controller.signal.aborted, true);
  assert.equal(triggered, 1);
});

test("si React no monta, a los diez segundos aparece error y diagnóstico de API", () => {
  const { events, timers, body, calls } = simulate();
  assert.equal(timers.length, 1);
  assert.equal(timers[0].delay, 10000);
  events.error({ message: "Uncaught SyntaxError: token inesperado", filename: "/_next/static/chunks/app.js?clave=oculta" });
  timers[0].handler();
  assert.equal(body.children.length, 1);
  const panel = body.children[0];
  assert.equal(panel.children[0].textContent, "VIEWTV no ha arrancado en 10 segundos");
  assert.match(panel.children[1].textContent, /SyntaxError/);
  assert.doesNotMatch(panel.children[1].textContent, /clave=oculta/);
  assert.equal(panel.children[2].textContent, "Proxy de API accesible (HTTP 401). El fallo está en el cliente.");
  assert.deepEqual(calls, [{ method: "GET", url: "/api/viewtv/auth/me" }]);
});

test("si React ya dejó la carga, no aparece un falso error", () => {
  const { timers, body, calls } = simulate(false);
  timers[0].handler();
  assert.equal(body.children.length, 0);
  assert.equal(calls.length, 0);
});
