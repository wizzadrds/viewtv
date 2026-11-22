"use client";

import { useEffect, useRef, useState } from "react";
import release from "@/app/release.json";

const UPDATE_INTERVAL_MS = 60_000;
const IDLE_RELOAD_MS = 90_000;
const SAFE_CHECK_MS = 15_000;

type ReleaseResponse = { revision?: string };

function safeToReload() {
  if (document.visibilityState !== "visible") return false;
  // No recargar durante vídeo, ficha/modal, ni introducción de datos.
  if (document.querySelector("[role='dialog'], video, [aria-modal='true']")) return false;
  if (document.querySelector("input:focus, textarea:focus, select:focus")) return false;
  const focused = document.activeElement;
  if (focused instanceof HTMLElement && focused.isContentEditable) return false;
  return true;
}

/** Las TVs consultan el mismo servidor que Windows, sin instalar código local. */
export default function AppUpdateMonitor() {
  const [available, setAvailable] = useState(false);
  const lastInteraction = useRef(0);

  useEffect(() => {
    lastInteraction.current = Date.now();
    const onInteraction = () => { lastInteraction.current = Date.now(); };
    for (const event of ["keydown", "pointerdown", "touchstart", "wheel"]) {
      window.addEventListener(event, onInteraction, { passive: true });
    }
    const controller = new AbortController();
    const check = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        const response = await fetch("/api/app-version", {
          cache: "no-store",
          credentials: "same-origin",
          headers: { Accept: "application/json" },
          signal: controller.signal,
        });
        if (!response.ok) return;
        const data = await response.json() as ReleaseResponse;
        if (typeof data.revision === "string"
            && /^v1-[a-zA-Z0-9-]{1,40}$/.test(data.revision)
            && data.revision !== release.revision) {
          setAvailable(true);
        }
      } catch {
        // Pérdida de red: no interrumpir al usuario; reintento periódico.
      }
    };
    void check();
    const interval = window.setInterval(() => { void check(); }, UPDATE_INTERVAL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void check();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("online", onVisible);
    return () => {
      controller.abort();
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("online", onVisible);
      for (const event of ["keydown", "pointerdown", "touchstart", "wheel"]) {
        window.removeEventListener(event, onInteraction);
      }
    };
  }, []);

  useEffect(() => {
    if (!available) return;
    const timer = window.setInterval(() => {
      if (Date.now() - lastInteraction.current >= IDLE_RELOAD_MS && safeToReload()) {
        window.location.reload();
      }
    }, SAFE_CHECK_MS);
    return () => window.clearInterval(timer);
  }, [available]);

  if (!available) return null;
  return (
    <aside className="viewtv-update-notice" role="status" aria-live="polite">
      <div>
        <strong>Hay una nueva versión de ViewTV</strong>
        <span>Se actualizará cuando dejes de usarla, nunca durante una película.</span>
      </div>
      <button
        className="viewtv-update-action"
        type="button"
        data-spatial
        onClick={() => window.location.reload()}
      >
        Actualizar ahora
      </button>
    </aside>
  );
}
