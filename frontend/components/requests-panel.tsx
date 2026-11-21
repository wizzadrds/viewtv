"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { apiRequest } from "@/lib/api";

type RequestItem = {
  id: number;
  titulo: string;
  tipo_medio: "pelicula" | "serie";
  anio: number | null;
  estado: string;
  creado_en: string;
};

type SearchResult = {
  id: number;
  titulo: string;
  indexador: string;
  seeders: number | null;
  peers: number | null;
  tamano_bytes: number | null;
  resolucion?: string | null;
};

type ResultVerification = {
  estado: "apto" | "bloqueado" | "no_verificable";
  puede_seleccionar: boolean;
  tamano_anunciado_bytes: number | null;
  tamano_real_bytes: number | null;
  advertencias: string[];
};

const REFRESH_MS = 10_000;

function describeState(state: string): string {
  const states: Record<string, string> = {
    pendiente: "Esperando la búsqueda",
    procesando: "Buscando resultados",
    vigilando: "Búsqueda en seguimiento",
    esperando_seleccion: "Resultados disponibles",
    sin_resultados: "No se encontraron resultados",
    fallida: "Búsqueda fallida; requiere revisión",
    completada: "Resultado seleccionado",
    cancelada: "Solicitud cancelada",
  };
  return states[state] ?? "Estado: " + state;
}

function describeSize(bytes: number | null): string {
  if (bytes === null || bytes <= 0) return "Tamaño desconocido";
  const value = bytes >= 1024 ** 3 ? bytes / 1024 ** 3 : bytes / 1024 ** 2;
  const unit = bytes >= 1024 ** 3 ? "GiB" : "MiB";
  return new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }).format(value) + " " + unit;
}

export default function RequestsPanel({
  onUnauthorized,
  onShowDownloads,
}: {
  onUnauthorized: () => void;
  onShowDownloads: () => void;
}) {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"pelicula" | "serie">("pelicula");
  const [year, setYear] = useState("");
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [verifications, setVerifications] = useState<Record<number, ResultVerification>>({});
  const [busy, setBusy] = useState(false);
  const [resultsBusy, setResultsBusy] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState("");
  const [resultsError, setResultsError] = useState("");
  const [notice, setNotice] = useState("");
  const lastRequest = useRef(0);
  const latestResults = useRef(0);

  const loadRequests = useCallback(async (signal?: AbortSignal) => {
    const requestId = ++lastRequest.current;
    try {
      const data = await apiRequest<RequestItem[]>(
        showHistory ? "/solicitudes" : "/solicitudes?solo_activas=true",
        { signal },
      );
      if (!signal?.aborted && requestId === lastRequest.current) {
        setRequests(data);
        setError("");
      }
    } catch (cause) {
      if (signal?.aborted || requestId !== lastRequest.current) return;
      if ((cause as Error & { status?: number }).status === 401) {
        onUnauthorized();
        return;
      }
      setError((cause as Error).message || "No se pudieron consultar las solicitudes.");
    } finally {
      if (!signal?.aborted && requestId === lastRequest.current) {
        setInitialLoading(false);
      }
    }
  }, [onUnauthorized, showHistory]);

  useEffect(() => {
    const controller = new AbortController();
    void loadRequests(controller.signal);
    const refreshVisible = () => {
      if (document.visibilityState === "visible") void loadRequests(controller.signal);
    };
    const interval = window.setInterval(refreshVisible, REFRESH_MS);
    document.addEventListener("visibilitychange", refreshVisible);
    return () => {
      controller.abort();
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", refreshVisible);
    };
  }, [loadRequests]);

  const visibleRequests = showHistory
    ? requests
    : requests.filter((request) =>
        ["pendiente", "procesando", "vigilando", "esperando_seleccion"].includes(request.estado),
      );
  const selectedRequest = visibleRequests.find((request) => request.id === selectedId);
  const canSelect = selectedRequest?.estado === "esperando_seleccion";

  useEffect(() => {
    if (!selectedId || !canSelect) {
      setResults([]);
      setResultsError("");
      return;
    }
    const controller = new AbortController();
    const fetchResults = async () => {
      const requestId = ++latestResults.current;
      setResultsBusy(true);
      try {
        const data = await apiRequest<SearchResult[]>(
          "/solicitudes/" + selectedId + "/resultados",
          { signal: controller.signal },
        );
        if (!controller.signal.aborted && requestId === latestResults.current) {
          setResults(data);
          setResultsError("");
        }
      } catch (cause) {
        if (controller.signal.aborted || requestId !== latestResults.current) return;
        if ((cause as Error & { status?: number }).status === 401) {
          onUnauthorized();
          return;
        }
        setResultsError(
          (cause as Error).message || "No se pudieron cargar los resultados.",
        );
      } finally {
        if (!controller.signal.aborted && requestId === latestResults.current) {
          setResultsBusy(false);
        }
      }
    };
    void fetchResults();
    const refreshVisible = () => {
      if (document.visibilityState === "visible") void fetchResults();
    };
    const interval = window.setInterval(refreshVisible, REFRESH_MS);
    document.addEventListener("visibilitychange", refreshVisible);
    return () => {
      controller.abort();
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", refreshVisible);
    };
  }, [selectedId, canSelect, onUnauthorized]);

  // Los tamaños se consultan automáticamente al abrir resultados, con
  // tres consultas simultáneas como máximo y sin repetir cada refresco.
  const resultIds = results.map((item) => item.id).join(",");
  useEffect(() => {
    if (!selectedId || !canSelect || !resultIds) return;
    const controller = new AbortController();
    const ids = resultIds.split(",").map(Number);
    let cursor = 0;
    const getNext = async () => {
      while (!controller.signal.aborted && cursor < ids.length) {
        const id = ids[cursor++];
        try {
          const check = await apiRequest<ResultVerification>(
            "/solicitudes/" + selectedId + "/resultados/" + id + "/verificacion",
            { signal: controller.signal },
          );
          if (!controller.signal.aborted) {
            setVerifications((previous) => ({ ...previous, [id]: check }));
          }
        } catch (cause) {
          if (controller.signal.aborted) break;
          if ((cause as Error & { status?: number }).status === 401) {
            onUnauthorized();
            break;
          }
          setVerifications((previous) => ({
            ...previous,
            [id]: {
              estado: "no_verificable",
              puede_seleccionar: false,
              tamano_anunciado_bytes: null,
              tamano_real_bytes: null,
              advertencias: ["No se pudo obtener el tamaño del torrent."],
            },
          }));
        }
      }
    };
    void Promise.all(
      Array.from({ length: Math.min(3, ids.length) }, () => getNext()),
    );
    return () => controller.abort();
  }, [selectedId, canSelect, resultIds, onUnauthorized]);

  async function createRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = title.trim();
    if (!normalized || busy || (year && (!Number.isInteger(Number(year)) || Number(year) < 1870 || Number(year) > 2200))) {
      return;
    }
    setBusy(true);
    setNotice("");
    setError("");
    try {
      await apiRequest("/solicitudes", {
        method: "POST",
        body: JSON.stringify({
          titulo: normalized,
          tipo_medio: kind,
          ...(year ? { anio: Number(year) } : {}),
        }),
      });
      setTitle("");
      setYear("");
      setSelectedId(null);
      setNotice("Solicitud registrada. VIEWTV buscará resultados y podrás elegir uno aquí.");
      await loadRequests();
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) {
        onUnauthorized();
        return;
      }
      setError((cause as Error).message || "No se pudo registrar la solicitud.");
    } finally {
      setBusy(false);
    }
  }

  async function chooseResult(resultId: number) {
    if (!verifications[resultId]?.puede_seleccionar) return;
    if (!selectedId || busy || !canSelect) return;
    setBusy(true);
    setNotice("");
    setResultsError("");
    try {
      await apiRequest("/solicitudes/" + selectedId + "/seleccion", {
        method: "POST",
        body: JSON.stringify({ resultado_id: resultId }),
      });
      setSelectedId(null);
      setResults([]);
      setVerifications({});
      setShowHistory(false);
      setNotice("Descarga solicitada. VIEWTV gestionará el envío y el inicio automáticamente. Consulta el progreso en Descargas.");
      await loadRequests();
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) {
        onUnauthorized();
        return;
      }
      setResultsError((cause as Error).message || "No se pudo seleccionar el resultado.");
      await loadRequests();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="requests-section" aria-labelledby="requests-title">
      <header className="downloads-heading">
        <div>
          <p className="eyebrow">ENCUENTRA CONTENIDO NUEVO</p>
          <h1 id="requests-title">Buscar y solicitar</h1>
          <p className="welcome-copy">
            Pide una película o serie. VIEWTV buscará opciones y podrás escoger el resultado.
          </p>
        </div>
        <span className="muted">Actualización automática cada 10 s</span>
      </header>

      <form className="requests-form" onSubmit={createRequest}>
        <label className="requests-field requests-title-field">
          <span>Título</span>
          <input
            data-spatial
            autoComplete="off"
            maxLength={500}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Título de la película o serie"
            required
            value={title}
          />
        </label>
        <label className="requests-field">
          <span>Tipo</span>
          <select
            data-spatial
            onChange={(event) => setKind(event.target.value as "pelicula" | "serie")}
            value={kind}
          >
            <option value="pelicula">Película</option>
            <option value="serie">Serie</option>
          </select>
        </label>
        <label className="requests-field requests-year-field">
          <span>Año (opcional)</span>
          <input
            data-spatial
            inputMode="numeric"
            max={2200}
            min={1870}
            onChange={(event) => setYear(event.target.value)}
            placeholder="Año"
            type="number"
            value={year}
          />
        </label>
        <button
          className="primary-button compact"
          data-spatial
          disabled={busy || !title.trim()}
          type="submit"
        >
          {busy ? "Guardando…" : "Solicitar búsqueda"}
        </button>
      </form>
      <p className="requests-note">
        VIEWTV obtiene automáticamente el tamaño de cada archivo .torrent.
        Al pulsar «Descargar», iniciará el proceso automáticamente.
        Selecciona solo contenido que tengas derecho a obtener.
      </p>

      {notice && (
        <p className="requests-notice" role="status">
          {notice}{" "}
          {notice.includes("Descarga solicitada") && (
            <button className="quiet-button" data-spatial onClick={onShowDownloads} type="button">
              Ver descargas
            </button>
          )}
        </p>
      )}
      {error && <p className="error-message" role="alert">{error}</p>}

      <div className="requests-heading">
        <h2>Mis solicitudes {showHistory ? "(historial)" : "(pendientes)"} <span className="count">{visibleRequests.length}</span></h2>
        <p className="muted">Las solicitudes finalizadas se ocultan para mantener esta lista limpia; se conservan en el historial.</p>
        <button
          className="quiet-button"
          data-spatial
          onClick={() => { setSelectedId(null); setShowHistory((current) => !current); }}
          type="button"
        >
          {showHistory ? "Ocultar historial" : "Ver historial"}
        </button>
      </div>
      {initialLoading && <p className="muted" role="status">Consultando solicitudes…</p>}
      {!initialLoading && visibleRequests.length === 0 && (
        <div className="empty-state">
          <h3>{showHistory ? "No hay solicitudes anteriores" : "No hay solicitudes pendientes"}</h3>
          <p>Busca un título nuevo o abre «Ver historial» para consultar las anteriores.</p>
        </div>
      )}
      <div className="requests-list">
        {visibleRequests.map((request) => (
          <article className="request-card" key={request.id}>
            <div className="download-item-header">
              <div className="download-item-copy">
                <h3>{request.titulo}</h3>
                <p className="download-item-meta">
                  {request.tipo_medio === "pelicula" ? "Película" : "Serie"}
                  {request.anio ? " · " + request.anio : ""}
                </p>
              </div>
              <span className="request-state">{describeState(request.estado)}</span>
            </div>
            {request.estado === "esperando_seleccion" && (
              <button
                className="quiet-button"
                data-spatial
                disabled={busy}
                onClick={() => {
                  setResults([]);
                  setVerifications({});
                  setResultsError("");
                  setSelectedId((current) => current === request.id ? null : request.id);
                }}
                type="button"
                aria-expanded={selectedId === request.id}
              >
                {selectedId === request.id ? "Ocultar resultados" : "Ver resultados"}
              </button>
            )}
            {request.estado === "fallida" && (
              <p className="muted">No se reintentará automáticamente. Puedes crear una solicitud nueva.</p>
            )}
            {selectedId === request.id && canSelect && (
              <div className="requests-results">
                {resultsBusy && results.length === 0 && (
                  <p className="muted" role="status">Cargando resultados…</p>
                )}
                {resultsError && <p className="error-message" role="alert">{resultsError}</p>}
                {!resultsBusy && !resultsError && results.length === 0 && (
                  <p className="muted">Ningún resultado coincide claramente con el título y tipo solicitados. Prueba otra búsqueda; no se pueden seleccionar coincidencias ajenas.</p>
                )}
                {results.map((result) => (
                  <div className="request-result" key={result.id}>
                    <div>
                      <p className="request-result-title">{result.titulo}</p>
                      <p className="download-item-meta">
                        {result.resolucion || "Resolución desconocida"}
                        {" · " + (
                          verifications[result.id]?.tamano_real_bytes != null
                            ? describeSize(verifications[result.id].tamano_real_bytes)
                            : verifications[result.id]
                              ? "Tamaño no disponible"
                              : "Consultando tamaño…"
                        )}
                        {" · " + (result.seeders ?? 0) + " fuentes"}
                      </p>
                      {verifications[result.id] &&
                        !verifications[result.id].puede_seleccionar && (
                          <p className="error-message" role="status">
                            {verifications[result.id].estado === "bloqueado"
                              ? "Torrent descartado anteriormente; no se descargará."
                              : "No se pudo obtener un torrent válido."}
                          </p>
                        )}
                    </div>
                    <div className="request-result-actions">
                      <button
                        className="primary-button compact"
                        data-spatial
                        disabled={busy || !verifications[result.id]?.puede_seleccionar}
                        onClick={() => void chooseResult(result.id)}
                        type="button"
                      >
                        Descargar
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
