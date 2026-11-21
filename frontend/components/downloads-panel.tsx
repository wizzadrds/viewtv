"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";
import type { DownloadItem, DownloadsResponse } from "@/lib/api";

const PAGE_SIZE = 20;
const REFRESH_MS = 15_000;

type StatusTone = "info" | "warning" | "success" | "error";

function describeDownload(item: DownloadItem): {
  title: string;
  detail: string;
  tone: StatusTone;
} {
  if (item.inicio_estado === "requiere_revision") {
    return {
      title: "Revisión necesaria",
      detail: "VIEWTV no intentará iniciarla otra vez automáticamente. Revisa el estado en qBittorrent.",
      tone: "warning",
    };
  }
  if (item.estado === "fallida") {
    return {
      title: "No se pudo procesar",
      detail: "La descarga ha fallado. Se necesita revisar su estado.",
      tone: "error",
    };
  }
  if (item.estado_verificacion === "fallida") {
    return {
      title: "Verificación fallida",
      detail: "Los archivos no han superado la comprobación. No están listos para reproducirse.",
      tone: "error",
    };
  }
  if (item.estado === "completada" && item.estado_verificacion === "verificada") {
    return {
      title: "Archivos verificados",
      detail: "Descarga comprobada. La organización en la biblioteca es una etapa posterior.",
      tone: "success",
    };
  }
  if (item.estado === "completada") {
    return {
      title: "Completada, pendiente de verificación",
      detail: "VIEWTV está comprobando los archivos antes de utilizarlos.",
      tone: "info",
    };
  }
  if (item.estado === "pausada") {
    return {
      title: "Pausada",
      detail: "La descarga está detenida; VIEWTV no la reanudará desde esta pantalla.",
      tone: "warning",
    };
  }
  if (item.estado === "descargando") {
    return {
      title: "Descargando",
      detail: "Transferencia detectada por el gestor de descargas.",
      tone: "info",
    };
  }
  if (item.inicio_estado === "pendiente") {
    return {
      title: "Inicio pendiente",
      detail: "La descarga aún no tiene un inicio confirmado. Si eliminaste el torrent de qBittorrent porque era incorrecto, puedes descartarlo aquí.",
      tone: "info",
    };
  }
  if (item.inicio_estado === "iniciada" && item.estado === "enviada") {
    return {
      title: "Inicio solicitado",
      detail: "Orden aceptada; esperando observar actividad en el gestor.",
      tone: "info",
    };
  }
  if (item.estado === "enviada") {
    return {
      title: "Enviada al gestor",
      detail: "A la espera de novedades del gestor de descargas.",
      tone: "info",
    };
  }
  if (item.estado === "seleccionada") {
    return {
      title: "Preparando descarga automática",
      detail: "VIEWTV está preparando el envío a qBittorrent; el porcentaje aparecerá cuando el gestor comience la transferencia.",
      tone: "info",
    };
  }
  return {
    title: "Pendiente",
    detail: "Esperando a que se actualice el estado de la selección.",
    tone: "info",
  };
}

function formatSize(bytes: number | null): string | null {
  if (bytes === null || bytes <= 0) return null;
  const size = bytes >= 1024 ** 3
    ? { value: bytes / (1024 ** 3), unit: "GiB" }
    : { value: bytes / (1024 ** 2), unit: "MiB" };
  return `${new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }).format(size.value)} ${size.unit}`;
}

export default function DownloadsPanel({
  onUnauthorized,
}: {
  onUnauthorized: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<DownloadsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [undoBusy, setUndoBusy] = useState<number | null>(null);
  const [reload, setReload] = useState(0);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    let latestRequest = 0;

    async function refresh(initial = false) {
      const requestId = ++latestRequest;
      if (initial) {
        setLoading(true);
        setError("");
      }

      try {
        const result = await apiRequest<DownloadsResponse>(
          `/solicitudes/descargas?limit=${PAGE_SIZE}&offset=${offset}`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted && requestId === latestRequest) {
          if (offset > 0 && offset >= result.total) {
            setOffset(Math.max(0, Math.ceil(result.total / PAGE_SIZE) - 1) * PAGE_SIZE);
            return;
          }
          setData(result);
          setError("");
        }
      } catch (cause) {
        if (controller.signal.aborted || requestId !== latestRequest) return;
        if ((cause as Error & { status?: number }).status === 401) {
          onUnauthorized();
          return;
        }
        setError(
          (cause as Error).message
          || "No se pudo actualizar el estado de las descargas.",
        );
      } finally {
        if (!controller.signal.aborted && requestId === latestRequest) {
          setLoading(false);
        }
      }
    }

    void refresh(true);
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    const intervalId = window.setInterval(refreshWhenVisible, REFRESH_MS);
    document.addEventListener("visibilitychange", refreshWhenVisible);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [offset, onUnauthorized, reload]);

  async function discardWrongSelection(id: number) {
    if (undoBusy !== null) return;
    if (!window.confirm(
      "¿Marcar esta selección como incorrecta? VIEWTV comprobará que el torrent ya no existe en qBittorrent. No borrará archivos ni otros torrents; la solicitud se conservará en el historial.",
    )) {
      return;
    }
    setUndoBusy(id);
    setError("");
    setNotice("");
    try {
      await apiRequest(`/solicitudes/descargas/${id}/descartar-incorrecta`, {
        method: "POST",
      });
      setNotice("Selección incorrecta descartada. Ya puedes buscar otra opción correcta.");
      setReload((current) => current + 1);
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) {
        onUnauthorized();
        return;
      }
      setError((cause as Error).message || "No se pudo descartar la selección.");
    } finally {
      setUndoBusy(null);
    }
  }

  async function undoSelection(id: number) {
    if (undoBusy !== null) return;
    if (!window.confirm("¿Deshacer esta selección que todavía no se ha enviado? Podrás elegir otro resultado desde Buscar y solicitar.")) {
      return;
    }
    setUndoBusy(id);
    setError("");
    setNotice("");
    try {
      await apiRequest(`/solicitudes/descargas/${id}/deshacer-seleccion`, { method: "POST" });
      setNotice("Selección retirada. Vuelve a «Buscar y solicitar» para elegir un resultado correcto.");
      setReload((current) => current + 1);
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) {
        onUnauthorized();
        return;
      }
      setError((cause as Error).message || "No se pudo deshacer la selección.");
    } finally {
      setUndoBusy(null);
    }
  }

  const entries = data?.elementos ?? [];
  const total = data?.total ?? 0;
  const nextAvailable = offset + PAGE_SIZE < total;

  return (
    <section className="downloads-section" aria-labelledby="downloads-title">
      <div className="downloads-heading">
        <div>
          <p className="eyebrow">SEGUIMIENTO DE DESCARGAS</p>
          <h1 id="downloads-title">Mis descargas <span className="count">{total}</span></h1>
          <p className="welcome-copy">
            Consulta el estado de tus selecciones. Esta pantalla no inicia ni reanuda torrents.
          </p>
        </div>
        <p className="muted">Se actualiza automáticamente</p>
      </div>

      {notice && <p className="requests-notice" role="status">{notice}</p>}
      {error && (
        <p className="error-message downloads-error" role="alert">
          No se pudo actualizar: {error}
          {data && " Se muestra la última información recibida."}
        </p>
      )}
      {loading && <p className="muted" role="status">Consultando tus descargas…</p>}

      {!loading && !error && entries.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon" aria-hidden="true">▤</div>
          <h2>No hay descargas que mostrar</h2>
          <p>Cuando selecciones una descarga, podrás consultar aquí su progreso y verificación.</p>
        </div>
      )}

      {!loading && entries.length > 0 && (
        <div className="downloads-list">
          {entries.map((item) => {
            const state = describeDownload(item);
            const sizeLabel = formatSize(item.tamano_bytes);
            const progress = Math.round(
              Math.max(0, Math.min(1, item.progreso)) * 100,
            );
            return (
              <article
                className={`download-item download-item--${state.tone}`}
                key={item.id}
              >
                <div className="download-item-header">
                  <div className="download-item-copy">
                    <h2>{item.titulo}</h2>
                    <p className="download-item-meta">
                      Solicitud #{item.solicitud_id}
                      {sizeLabel && ` · ${sizeLabel}`}
                    </p>
                  </div>
                  <span className={`download-status download-status--${state.tone}`}>
                    {state.title}
                  </span>
                </div>
                <p className="download-detail">{state.detail}</p>
                {item.estado === "enviada" && item.inicio_estado === "pendiente" && item.progreso === 0 && (
                  <button
                    className="quiet-button"
                    data-spatial
                    disabled={undoBusy !== null}
                    onClick={() => void discardWrongSelection(item.id)}
                    type="button"
                  >
                    {undoBusy === item.id ? "Comprobando…" : "Descartar torrent incorrecto"}
                  </button>
                )}
                {item.estado === "seleccionada" && (
                  <button
                    className="quiet-button"
                    data-spatial
                    disabled={undoBusy !== null}
                    onClick={() => void undoSelection(item.id)}
                    type="button"
                  >
                    {undoBusy === item.id ? "Deshaciendo…" : "Deshacer selección"}
                  </button>
                )}
                <div className="download-progress-row">
                  <progress
                    aria-label={`Progreso de ${item.titulo}`}
                    max={100}
                    value={progress}
                  />
                  <span className="download-percent">{progress} %</span>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {!loading && total > PAGE_SIZE && (
        <div className="downloads-pagination">
          <span>Mostrando {Math.min(offset + 1, total)}–{Math.min(offset + entries.length, total)} de {total}</span>
          <div className="downloads-pagination-actions">
            <button
              className="quiet-button"
              data-spatial
              disabled={offset === 0}
              onClick={() => {
                setData(null);
                setOffset((old) => Math.max(0, old - PAGE_SIZE));
              }}
              type="button"
            >← Anteriores</button>
            <button
              className="quiet-button"
              data-spatial
              disabled={!nextAvailable}
              onClick={() => {
                setData(null);
                setOffset((old) => old + PAGE_SIZE);
              }}
              type="button"
            >Siguientes →</button>
          </div>
        </div>
      )}
      <p className="downloads-note">Actualización automática cada 15 segundos mientras la pestaña esté visible.</p>
    </section>
  );
}
