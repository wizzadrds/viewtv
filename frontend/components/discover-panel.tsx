"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { apiRequest } from "@/lib/api";
import DiscoveryRows from "@/components/discovery-rows";

type Tipo = "pelicula" | "serie";

type DiscoveryItem = {
  tmdb_id: number | null;
  tipo: Tipo;
  titulo: string;
  sinopsis: string | null;
  anio: number | null;
  imagen_portada: string | null;
  imagen_fondo: string | null;
  disponible_local: boolean;
  medio_id: number | null;
  generos?: string[];
  duracion_minutos?: number | null;
};

type DiscoveryPage = {
  elementos: DiscoveryItem[];
  pagina: number;
  paginas: number;
};

export default function DiscoverPanel({
  onUnauthorized,
  onShowRequests,
  onShowLibrary,
}: {
  onUnauthorized: () => void;
  onShowRequests: () => void;
  onShowLibrary: (mediaId?: number) => void;
}) {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [kind, setKind] = useState<Tipo>("pelicula");
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState("");
  const [page, setPage] = useState(1);
  const [results, setResults] = useState<DiscoveryItem[]>([]);
  const [pages, setPages] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<DiscoveryItem | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [requestBusy, setRequestBusy] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    apiRequest<{ tmdb_configurado: boolean }>("/descubrir/estado")
      .then((data) => { if (active) setConfigured(data.tmdb_configurado); })
      .catch((cause) => {
        if (!active) return;
        if ((cause as Error & { status?: number }).status === 401) onUnauthorized();
        else setError("No se pudo consultar la configuración del catálogo.");
      });
    return () => { active = false; };
  }, [onUnauthorized]);

  useEffect(() => {
    if (configured !== true || !searched) return;
    const controller = new AbortController();
    const load = async () => {
      setBusy(true);
      setError("");
      try {
        const params = new URLSearchParams({ tipo: kind, pagina: String(page) });
        const endpoint = searched
          ? (params.set("titulo", searched), "/descubrir/buscar")
          : "/descubrir/tendencias";
        const response = await apiRequest<DiscoveryPage>(
          endpoint + "?" + params.toString(), { signal: controller.signal },
        );
        if (!controller.signal.aborted) {
          setResults(response.elementos);
          setPages(response.paginas);
        }
      } catch (cause) {
        if (controller.signal.aborted) return;
        if ((cause as Error & { status?: number }).status === 401) {
          onUnauthorized();
        } else {
          setError((cause as Error).message || "No se pudieron obtener los metadatos.");
        }
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    };
    void load();
    return () => controller.abort();
  }, [configured, kind, page, searched, onUnauthorized]);

  const runSearch = useCallback((event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = query.trim();
    if (value.length < 2 || value.length > 100) return;
    setPage(1);
    setSearched(value);
    setDetail(null);
  }, [query]);

  const openDetail = async (item: DiscoveryItem) => {
    if (item.disponible_local && item.medio_id != null) {
      onShowLibrary(item.medio_id);
      return;
    }
    if (item.tmdb_id === null) return;
    setDetail(item);
    setDetailBusy(true);
    setNotice("");
    try {
      const fresh = await apiRequest<DiscoveryItem>(
        "/descubrir/" + item.tipo + "/" + item.tmdb_id,
      );
      setDetail(fresh);
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) onUnauthorized();
      else setNotice("No se pudo actualizar la ficha. Puedes volver a intentarlo.");
    } finally {
      setDetailBusy(false);
    }
  };

  const requestDownload = async (item: DiscoveryItem) => {
    if (requestBusy || item.disponible_local || detailBusy || item.tmdb_id === null) return;
    setRequestBusy(true);
    setNotice("");
    try {
      await apiRequest(
        "/descubrir/" + item.tipo + "/" + item.tmdb_id + "/solicitar",
        { method: "POST" },
      );
      setNotice(
        "Solicitud creada. No se descargará nada hasta que elijas una fuente autorizada en «Buscar y pedir».",
      );
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) {
        onUnauthorized();
        return;
      }
      setNotice((cause as Error).message || "No se pudo solicitar el contenido.");
    } finally {
      setRequestBusy(false);
    }
  };

  return (
    <section className="discover-section" aria-labelledby="discover-title">
      <header className="discover-heading">
        <p className="eyebrow">CATÁLOGO SIN OCUPAR ESPACIO EN EL DISCO</p>
        <h1 id="discover-title">Explora películas y series</h1>
        <p className="welcome-copy">
          Descubre títulos, carátulas y sinopsis. Ver una ficha nunca descarga el vídeo.
        </p>
      </header>

      {configured === null && !error && <p className="muted">Comprobando el catálogo de metadatos…</p>}

      {!searched && (
        <DiscoveryRows
          onOpen={(item) => void openDetail(item)}
          onUnauthorized={onUnauthorized}
          onShowLibrary={() => onShowLibrary()}
        />
      )}

      {configured === true && (
        <>
          <form className="discover-search" onSubmit={runSearch}>
            <label htmlFor="discover-query">Buscar películas o series</label>
            <div className="discover-search-line">
              <input id="discover-query" type="search" data-spatial
                placeholder="Escribe un título…" value={query} maxLength={100}
                onChange={(event) => setQuery(event.target.value)}
              />
              <button className="primary-button compact" data-spatial type="submit"
                disabled={query.trim().length < 2 || busy}>Buscar</button>
            </div>
          </form>

          <div className="filter-row" aria-label="Tipo de contenido">
            {([["pelicula", "Películas"], ["serie", "Series"]] as const).map(([value, label]) => (
              <button key={value} type="button" data-spatial
                className={kind === value ? "filter-chip active" : "filter-chip"}
                onClick={() => { setKind(value); setPage(1); setDetail(null); }}>
                {label}
              </button>
            ))}
            {searched && (
              <button type="button" data-spatial className="quiet-button" onClick={() => {
                setQuery(""); setSearched(""); setPage(1); setDetail(null);
              }}>Volver a tendencias</button>
            )}
          </div>

          {searched && (
          <>
          <h2 className="discover-list-title">
            {searched ? "Resultados para «" + searched + "»" : "Tendencias de la semana"}
          </h2>
          {error && <p className="error-message" role="alert">{error}</p>}
          {busy && <p className="muted" role="status">Cargando fichas…</p>}
          {!busy && !error && results.length === 0 && (
            <p className="muted">No se encontraron títulos. Prueba otra búsqueda.</p>
          )}

          <div className="discover-grid">
            {results.map((item) => (
              <button type="button" data-spatial className="discover-card"
                key={item.tipo + "-" + item.tmdb_id}
                onClick={() => void openDetail(item)}>
                <span className="discover-poster">
                  {item.imagen_portada ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img alt="" src={item.imagen_portada} loading="lazy" />
                  ) : <span className="poster-placeholder">VIEWTV</span>}
                  <span className={item.disponible_local ? "discover-status installed" : "discover-status"}>
                    {item.disponible_local ? "En tu biblioteca" : "Sin descargar"}
                  </span>
                </span>
                <span className="media-title">{item.titulo}</span>
                <span className="media-meta">
                  {item.anio ?? "Año desconocido"} · {item.tipo === "pelicula" ? "Película" : "Serie"}
                </span>
              </button>
            ))}
          </div>

          {pages > 1 && (
            <div className="discover-pages">
              <button type="button" data-spatial className="quiet-button"
                disabled={page <= 1 || busy} onClick={() => setPage(page - 1)}>Anterior</button>
              <span className="muted">Página {page} de {pages}</span>
              <button type="button" data-spatial className="quiet-button"
                disabled={page >= pages || busy} onClick={() => setPage(page + 1)}>Siguiente</button>
            </div>
          )}

          </>
          )}
          <div className="discover-credit tmdb-credit" aria-label="Créditos de los metadatos">
            <a href="https://www.themoviedb.org/" target="_blank" rel="noopener noreferrer"
              aria-label="The Movie Database: fuente de metadatos">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/tmdb-logo.svg" alt="TMDB" />
            </a>
            <p>
              Este producto utiliza la API de TMDB, pero no está respaldado ni certificado por TMDB.
              Las carátulas y fichas son metadatos; que un título aparezca aquí no garantiza
              disponibilidad de una fuente autorizada ni inicia descargas.
            </p>
          </div>
        </>
      )}

      {detail && (
        <div className="dialog-backdrop" role="presentation" onClick={() => setDetail(null)}>
          <section className="detail-dialog" role="dialog" aria-modal="true"
            aria-labelledby="discovery-detail-title" onClick={(event) => event.stopPropagation()}>
            <button className="dialog-close" type="button" data-spatial
              aria-label="Cerrar ficha" onClick={() => setDetail(null)}>×</button>
            {detail.imagen_fondo && (
              // eslint-disable-next-line @next/next/no-img-element
              <img alt="" className="detail-backdrop" src={detail.imagen_fondo} />
            )}
            <div className="detail-content">
              <div className={detail.imagen_portada ? "detail-layout has-poster" : "detail-layout"}>
                {detail.imagen_portada && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img alt="" className="detail-poster" src={detail.imagen_portada} />
                )}
                <div className="detail-copy">
                  <p className="eyebrow">{detail.tipo === "pelicula" ? "PELÍCULA" : "SERIE"}</p>
                  <h2 id="discovery-detail-title">{detail.titulo}</h2>
                  <p className="detail-meta">
                    {detail.anio ?? "Año desconocido"}
                    {detail.generos?.length ? " · " + detail.generos.join(" · ") : ""}
                    {detail.duracion_minutos ? " · " + detail.duracion_minutos + " min" : ""}
                  </p>
                  <p className="detail-synopsis">{detail.sinopsis || "Sin sinopsis disponible."}</p>
                  <p className="discover-availability">
                    {detail.disponible_local
                      ? "Disponible para reproducir desde tu biblioteca"
                      : "Ficha disponible · Vídeo no descargado"}
                  </p>
                  {detail.disponible_local ? (
                    <>
                      <button className="primary-button compact" type="button" data-spatial
                        onClick={() => { setDetail(null); onShowLibrary(); }}>
                        Ir a mi biblioteca
                      </button>
                      <button type="button" className="quiet-button" disabled
                        title="El borrado seguro de archivos propios aún está en desarrollo.">
                        Desinstalar (pendiente)
                      </button>
                      <p className="small-note muted">
                        Desinstalar solo estará disponible después de comprobar que la copia es
                        propiedad de ViewTV y no está en uso. No se borrarán torrents ajenos.
                      </p>
                    </>
                  ) : (
                    <button className="primary-button compact" type="button" data-spatial
                      disabled={requestBusy || detailBusy}
                      onClick={() => void requestDownload(detail)}>
                      {requestBusy ? "Creando solicitud…" : "Descargar"}
                    </button>
                  )}
                  {detailBusy && <p className="muted">Actualizando datos de la ficha…</p>}
                  {notice && (
                    <div role="status" className="discover-notice">
                      <p>{notice}</p>
                      {notice.startsWith("Solicitud creada") && (
                        <button className="quiet-button" type="button" data-spatial onClick={() => {
                          setDetail(null); onShowRequests();
                        }}>Elegir fuente en «Buscar y pedir»</button>
                      )}
                    </div>
                  )}
                  <button className="quiet-button" data-spatial type="button"
                    onClick={() => { setDetail(null); setNotice(""); }}>
                    Volver a explorar
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
