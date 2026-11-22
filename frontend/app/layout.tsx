import type { Metadata, Viewport } from "next";
import "./globals.css";
import AppUpdateMonitor from "@/components/app-update-monitor";

export const metadata: Metadata = {
  title: "VIEWTV",
  description: "Tu biblioteca multimedia en casa.",
  applicationName: "VIEWTV",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#090b12",
  width: "device-width",
  initialScale: 1,
};

// Se ejecuta antes de los bundles de Next: también funciona si React no puede hidratar.
const bootGuard = `
(function () {
  "use strict";
  // Tizen 5.0 (Chromium 63) no tiene AbortController; las vistas comprueban signal.aborted.
  if (typeof window.AbortController !== "function") {
    window.AbortController = function () {
      var signal = { aborted: false, onabort: null, _listeners: [] };
      signal.addEventListener = function (type, fn) {
        if (type === "abort" && typeof fn === "function") signal._listeners.push(fn);
      };
      signal.removeEventListener = function (type, fn) {
        if (type !== "abort") return;
        var pos = signal._listeners.indexOf(fn);
        if (pos !== -1) signal._listeners.splice(pos, 1);
      };
      this.signal = signal;
      this.abort = function () {
        if (signal.aborted) return;
        signal.aborted = true;
        var event = { type: "abort" };
        if (typeof signal.onabort === "function") signal.onabort(event);
        for (var i = 0; i < signal._listeners.length; i++) signal._listeners[i](event);
      };
    };
  }

  var jsError = "";
  window.addEventListener("error", function (event) {
    if (event.message) {
      var file = event.filename ? event.filename.split("/").pop().split("?")[0] : "";
      jsError = String(event.message).slice(0, 150) + (file ? " · " + file : "");
    } else if (event.target && event.target.tagName === "SCRIPT") {
      jsError = "No se pudo cargar un archivo JavaScript.";
    }
  }, true);
  window.addEventListener("unhandledrejection", function (event) {
    if (!jsError) {
      var reason = event.reason;
      jsError = "Promesa rechazada: " + String(reason && reason.name || "error no identificado");
    }
  });

  window.setTimeout(function () {
    if (!document.querySelector(".boot-screen")) return;
    var panel = document.createElement("section");
    panel.id = "viewtv-boot-diagnostic";
    panel.setAttribute("role", "alert");
    panel.style.cssText = "position:fixed;z-index:2147483647;left:5%;right:5%;top:12%;padding:24px;background:#30172d;border:2px solid #ffd4e4;border-radius:12px;color:white;font:18px Arial,sans-serif;max-height:75vh;overflow:auto";
    var title = document.createElement("h2");
    title.textContent = "VIEWTV no ha arrancado en 10 segundos";
    panel.appendChild(title);
    var detail = document.createElement("p");
    detail.textContent = jsError ? "Error de JavaScript: " + jsError : "No se completó la hidratación de React. Puede faltar un bundle o haber una incompatibilidad del navegador.";
    panel.appendChild(detail);
    var apiStatus = document.createElement("p");
    apiStatus.textContent = "Comprobando el proxy de la API…";
    panel.appendChild(apiStatus);
    var link = document.createElement("a");
    link.href = "/tv.html";
    link.textContent = "Abrir versión Samsung compatible";
    link.style.cssText = "display:inline-block;color:white;background:#63439e;padding:12px;border:1px solid white;border-radius:7px";
    panel.appendChild(link);
    document.body.appendChild(panel);

    var xhr = new XMLHttpRequest();
    xhr.open("GET", "/api/viewtv/auth/me", true);
    xhr.timeout = 2500;
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return;
      apiStatus.textContent = xhr.status === 200 || xhr.status === 401
        ? "Proxy de API accesible (HTTP " + xhr.status + "). El fallo está en el cliente."
        : "El proxy de API respondió HTTP " + xhr.status + ".";
    };
    xhr.ontimeout = function () { apiStatus.textContent = "La API no respondió en 2,5 segundos."; };
    xhr.onerror = function () { apiStatus.textContent = "No se pudo consultar /api/viewtv/auth/me."; };
    try { xhr.send(null); } catch (error) { apiStatus.textContent = "Error al consultar el proxy de API."; }
  }, 10000);
})();
`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <head>
        <script dangerouslySetInnerHTML={{ __html: bootGuard }} />
      </head>
      <body>
        <AppUpdateMonitor />
        {children}
      </body>
    </html>
  );
}
