import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const html = readFileSync(new URL("../public/tv.html", import.meta.url), "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script, "La página Samsung contiene un script autónomo");

function simulate(responses) {
  const calls = [];
  const timers = [];
  const nodes = new Map();

  function element(tag) {
    return {
      tagName: tag.toUpperCase(),
      children: [],
      className: "",
      textContent: "",
      style: {},
      disabled: false,
      appendChild(node) { this.children.push(node); return node; },
      removeChild(node) {
        const index = this.children.indexOf(node);
        if (index !== -1) this.children.splice(index, 1);
        return node;
      },
      get firstChild() { return this.children[0] || null; },
      setAttribute() {},
      focus() {},
    };
  }
  for (const id of ["main", "status", "nav", "update", "reload"]) {
    nodes.set(id, element("div"));
  }
  const document = {
    getElementById(id) { return nodes.get(id) || null; },
    createElement: element,
    addEventListener() {},
  };
  class MockXHR {
    open(method, path) { this.method = method; this.path = path; }
    setRequestHeader() {}
    send(body) {
      calls.push({ method: this.method, path: this.path, body });
      const result = responses[this.path] || { status: 404, data: null };
      this.status = result.status;
      this.responseText = JSON.stringify(result.data);
      this.readyState = 4;
      this.onreadystatechange?.();
    }
  }
  const window = { location: { reload() {} } };
  vm.runInNewContext(script, {
    document,
    window,
    XMLHttpRequest: MockXHR,
    setInterval(handler, ms) { timers.push({ handler, ms }); },
    Date,
    String,
    JSON,
    encodeURIComponent,
  }, { timeout: 3000 });
  return { nodes, calls, timers };
}

test("Samsung: sesión sin autenticar abre perfiles por el proxy same-origin", () => {
  const { calls, nodes, timers } = simulate({
    "/api/app-version": { status: 200, data: { revision: "v1-prueba" } },
    "/api/viewtv/auth/me": { status: 401, data: { detail: "No autenticado" } },
    "/api/viewtv/auth/profiles": {
      status: 200, data: { perfiles: [{ id: 1, nombre: "Perfil ficticio" }] },
    },
  });
  assert.deepEqual(calls.map(({ method, path }) => [method, path]), [
    ["GET", "/api/app-version"],
    ["GET", "/api/viewtv/auth/me"],
    ["GET", "/api/viewtv/auth/profiles"],
  ]);
  assert.equal(nodes.get("main").children[0].textContent, "¿Quién está viendo?");
  assert.equal(nodes.get("main").children[1].children.length, 1);
  assert.equal(nodes.get("main").children[1].children[0].textContent, "Perfil ficticio");
  assert.equal(timers.length, 1);
  assert.equal(timers[0].ms, 60000);
});

test("Samsung: un fallo de perfiles muestra un error y un botón de reintento", () => {
  const { nodes, calls } = simulate({
    "/api/app-version": { status: 200, data: { revision: "v1-prueba" } },
    "/api/viewtv/auth/me": { status: 401, data: null },
    "/api/viewtv/auth/profiles": { status: 503, data: null },
  });
  const main = nodes.get("main");
  assert.match(main.children[0].textContent, /No se pudieron obtener los perfiles/);
  assert.equal(main.children[1].textContent, "Volver a intentar");
  assert.equal(calls.length, 3);
});

test("Samsung: la sesión activa permite abrir Explorar sin POST ni torrent", () => {
  const { nodes, calls } = simulate({
    "/api/app-version": { status: 200, data: { revision: "v1-prueba" } },
    "/api/viewtv/auth/me": { status: 200, data: { id: 1, nombre: "Perfil ficticio" } },
    "/api/viewtv/descubrir/filas": { status: 200, data: { filas: [] } },
  });
  assert.equal(nodes.get("main").children[0].textContent, "Tu catálogo");
  assert.ok(nodes.get("nav").children.some((n) => n.textContent === "Explorar"));
  assert.ok(calls.every((c) => c.method === "GET"));
  assert.ok(calls.every((c) => c.path.startsWith("/api/")));
});
