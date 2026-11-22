"use client";

import { useEffect, useRef, useState } from "react";
import { apiPath, apiRequest } from "@/lib/api";

type Kind = "pelicula" | "serie";
export type ShelfItem = {
  tmdb_id: number | null;
  medio_id: number | null;
  tipo: Kind;
  titulo: string;
  sinopsis: string | null;
  anio: number | null;
  generos?: string[];
  imagen_portada: string | null;
  imagen_fondo: string | null;
  disponible_local: boolean;
  duracion_minutos?: number | null;
};

type Shelf = {
  id: string;
  titulo: string;
  descripcion: string;
  origen: "local" | "genero" | "anio" | "tendencia" | "cache";
  tipo: Kind;
};
type ShelfResponse = { filas: Shelf[]; tmdb_configurado: boolean };
type ShelfData = { id: string; elementos: ShelfItem[]; pagina?: number; paginas?: number; total?: number };
type CatalogStatus = { total: number; peliculas: number; series: number; ultima_actualizacion: string | null };

function imagePath(url: string | null): string | null {
  if (!url) return null;
  if (url.startsWith("/jellyfin/media/")) return apiPath(url);
  if (url.startsWith("https://image.tmdb.org/t/p/")) return url;
  return null;
}

export default function DiscoveryRows({
  onOpen,
  onUnauthorized,
  onShowLibrary,
}: {
  onOpen: (item: ShelfItem) => void;
  onUnauthorized: () => void;
  onShowLibrary: () => void;
}) {
  const [shelves, setShelves] = useState<Shelf[]>([]);
  const [configured, setConfigured] = useState(false);
  const [items, setItems] = useState<Record<string, ShelfItem[]>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, boolean>>({});
  const [pageNumbers, setPageNumbers] = useState<Record<string, number>>({});
  const [pageCounts, setPageCounts] = useState<Record<string, number>>({});
  const [totalCounts, setTotalCounts] = useState<Record<string, number>>({});
  const [moreBusy, setMoreBusy] = useState<Record<string, boolean>>({});
  const [catalogStatus, setCatalogStatus] = useState<CatalogStatus | null>(null);
  const [loadError, setLoadError] = useState("");
  const strips = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const listing = await apiRequest<ShelfResponse>(
          "/descubrir/filas", { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        setShelves(listing.filas);
        setConfigured(listing.tmdb_configurado);
        void apiRequest<CatalogStatus>("/descubrir/catalogo/estado", { signal: controller.signal })
          .then((status) => { if (!controller.signal.aborted) setCatalogStatus(status); })
          .catch(() => { /* Si falta la caché, el catálogo TMDB actual sigue disponible. */ });
        // El primer carrusel de la biblioteca se carga incluso SIN TMDB.
        const jobs = listing.filas.filter(
          (shelf) => shelf.origen === "local" || listing.tmdb_configurado,
        );
        setLoading(Object.fromEntries(jobs.map((row) => [row.id, true])));
        let next = 0;
        const worker = async () => {
          while (next < jobs.length && !controller.signal.aborted) {
            const shelf = jobs[next++];
            try {
              const data = await apiRequest<ShelfData>(
                "/descubrir/filas/" + encodeURIComponent(shelf.id),
                { signal: controller.signal },
              );
              if (!controller.signal.aborted) {
                setItems((previous) => ({ ...previous, [shelf.id]: data.elementos }));
                setPageNumbers((previous) => ({ ...previous, [shelf.id]: data.pagina ?? 1 }));
                setPageCounts((previous) => ({ ...previous, [shelf.id]: data.paginas ?? 1 }));
                if (typeof data.total === "number") {
                  setTotalCounts((previous) => ({ ...previous, [shelf.id]: data.total! }));
                }
              }
            } catch (cause) {
              if (controller.signal.aborted) return;
              if ((cause as Error & { status?: number }).status === 401) {
                onUnauthorized();
                return;
              }
              setErrors((previous) => ({ ...previous, [shelf.id]: true }));
            } finally {
              if (!controller.signal.aborted) {
                setLoading((previous) => ({ ...previous, [shelf.id]: false }));
              }
            }
          }
        };
        // Evitar saturar el API de TMDB: hasta dos peticiones simultáneas.
        await Promise.all([worker(), worker()]);
      } catch (cause) {
        if (controller.signal.aborted) return;
        if ((cause as Error & { status?: number }).status === 401) onUnauthorized();
        else setLoadError("No se pudieron cargar las categorías de ViewTV.");
      }
    };
    void load();
    return () => controller.abort();
  }, [onUnauthorized]);

  const loadNext = async (id: string) => {
    if (moreBusy[id] || (pageNumbers[id] ?? 1) >= (pageCounts[id] ?? 1)) return;
    const next = (pageNumbers[id] ?? 1) + 1;
    setMoreBusy((previous) => ({ ...previous, [id]: true }));
    try {
      const data = await apiRequest<ShelfData>(
        "/descubrir/filas/" + encodeURIComponent(id) + "?pagina=" + next,
      );
      setItems((previous) => {
        const known = new Set((previous[id] ?? []).map((item) => item.tipo + "-" + item.tmdb_id));
        const additions = data.elementos.filter((item) => !known.has(item.tipo + "-" + item.tmdb_id));
        return { ...previous, [id]: [...(previous[id] ?? []), ...additions] };
      });
      setPageNumbers((previous) => ({ ...previous, [id]: next }));
      setPageCounts((previous) => ({ ...previous, [id]: data.paginas ?? next }));
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) onUnauthorized();
      else setErrors((previous) => ({ ...previous, [id]: true }));
    } finally {
      setMoreBusy((previous) => ({ ...previous, [id]: false }));
    }
  };

  const featured = items["recientes"]?.[0]
    ?? shelves.flatMap((row) => items[row.id] ?? []).find(
      (item) => item.imagen_fondo || item.imagen_portada,
    );
  const featuredBackdrop = imagePath(featured?.imagen_fondo ?? featured?.imagen_portada ?? null);

  const slide = (id: string, direction: number) => {
    const strip = strips.current[id];
    if (strip) {
      strip.scrollBy({
        left: Math.round(strip.clientWidth * 0.8) * direction,
        behavior: "smooth",
      });
    }
  };

  if (loadError) return <p className="error-message" role="alert">{loadError}</p>;

  return (
    <div className="cinema-home" aria-label="Categorías de películas y series">
      <section className="cinema-hero" aria-labelledby="cinema-hero-title">
        {featuredBackdrop && (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="cinema-hero-art" src={featuredBackdrop} alt="" />
        )}
        <div className="cinema-hero-shade" />
        <div className="cinema-hero-body">
          <span className="cinema-hero-kicker">
            <span className="cinema-live-dot" /> TU CINE EN CASA
          </span>
          {catalogStatus && catalogStatus.total > 0 && (
            <p className="cinema-catalog-counter">
              <strong>{catalogStatus.total.toLocaleString("es-ES")}</strong> fichas únicas en el catálogo
              <span> · {catalogStatus.peliculas.toLocaleString("es-ES")} películas y {catalogStatus.series.toLocaleString("es-ES")} series</span>
            </p>
          )}
          <h2 id="cinema-hero-title">
            {featured ? featured.titulo : <>Un universo de historias <em>a tu manera.</em></>}
          </h2>
          <p>
            {featured
              ? (featured.sinopsis?.slice(0, 185) || "Disponible en tu biblioteca.")
              : "Explora, elige qué ver y descarga solo lo que quieras conservar."}
          </p>
          <div className="cinema-hero-buttons">
            {featured && (
              <button type="button" data-spatial className="primary-button"
                onClick={() => onOpen(featured)}>
                Ver ficha
              </button>
            )}
            <button type="button" data-spatial className="cinema-outline-button"
              onClick={onShowLibrary}>Mi biblioteca</button>
          </div>
        </div>
      </section>

      {shelves.filter((shelf) => shelf.origen === "local" || configured).map((shelf) => {
        const content = items[shelf.id] ?? [];
        const isLoading = loading[shelf.id] === true;
        // Una categoría vacía del proveedor no muestra tarjetas ficticias.
        if (!isLoading && content.length === 0 && !errors[shelf.id]
            && shelf.origen !== "local") return null;

        return (
          <section key={shelf.id} className="cinema-shelf"
            aria-labelledby={"shelf-" + shelf.id}>
            <div className="cinema-shelf-heading">
              <div>
                <h3 id={"shelf-" + shelf.id}>{shelf.titulo}</h3>
                <p>{shelf.descripcion}</p>
                {totalCounts[shelf.id] > 20 && (
                  <span className="cinema-row-counter">
                    {content.length.toLocaleString("es-ES")} de {totalCounts[shelf.id].toLocaleString("es-ES")} fichas
                  </span>
                )}
              </div>
              <div className="cinema-shelf-arrows">
                <button type="button" data-spatial aria-label={"Desplazar a la izquierda: " + shelf.titulo}
                  onClick={() => slide(shelf.id, -1)} disabled={!content.length}>‹</button>
                <button type="button" data-spatial aria-label={"Desplazar a la derecha: " + shelf.titulo}
                  onClick={() => slide(shelf.id, 1)} disabled={!content.length}>›</button>
              </div>
            </div>

            {errors[shelf.id] && (
              <p className="muted cinema-shelf-message">
                No se ha podido cargar esta categoría. Las demás siguen disponibles.
              </p>
            )}
            {isLoading && (
              <div className="cinema-shelf-loading" aria-label={"Cargando " + shelf.titulo} role="status">
                {Array.from({ length: 6 }, (_, i) => <div key={i} className="cinema-skeleton" />)}
              </div>
            )}
            {!isLoading && !errors[shelf.id] && shelf.origen === "local" && content.length === 0 && (
              <p className="muted cinema-shelf-message">
                Aún no hay títulos en tu biblioteca. Las fichas se mostrarán aquí sin descargarlas.
              </p>
            )}
            {content.length > 0 && !isLoading && (
              <div className="cinema-shelf-track" ref={(node) => { strips.current[shelf.id] = node; }}>
                {content.map((item) => {
                  const poster = imagePath(item.imagen_portada ?? item.imagen_fondo);
                  return (
                    <button key={(item.tipo ?? "pelicula") + "-" + (item.tmdb_id ?? "local-" + item.medio_id)}
                      data-spatial type="button" className="cinema-tile"
                      aria-label={item.titulo + (item.disponible_local ? ", disponible en tu biblioteca" : ", sin descargar")}
                      onClick={() => onOpen(item)}>
                      <span className="cinema-tile-image">
                        {poster ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={poster} alt="" loading="lazy" />
                        ) : <span className="cinema-tile-no-image">VIEWTV</span>}
                        {item.disponible_local && <span className="cinema-tile-ready">Disponible</span>}
                        {!item.disponible_local && <span className="cinema-tile-cloud">Sin descargar</span>}
                      </span>
                      <span className="cinema-tile-name">{item.titulo}</span>
                      <span className="cinema-tile-meta">
                        {item.anio ?? "—"} · {item.tipo === "serie" ? "Serie" : "Película"}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
            {content.length > 0 && !isLoading && (pageNumbers[shelf.id] ?? 1) < (pageCounts[shelf.id] ?? 1) && (
              <div className="cinema-more-row">
                <button type="button" data-spatial className="cinema-outline-button"
                  disabled={moreBusy[shelf.id]}
                  onClick={() => { void loadNext(shelf.id); }}>
                  {moreBusy[shelf.id] ? "Cargando más títulos…" : "Ver 20 títulos más"}
                </button>
                <span className="muted">Página {pageNumbers[shelf.id] ?? 1} de {pageCounts[shelf.id]}</span>
              </div>
            )}
          </section>
        );
      })}

      {!configured && shelves.length > 0 && (
        <aside className="cinema-config-message">
          <span className="cinema-config-icon" aria-hidden="true">✦</span>
          <div>
            <strong>Más películas, series, terror, acción y estrenos de {new Date().getFullYear()}</strong>
            <p>
              Las nuevas categorías se activarán al configurar TMDB_API_KEY
              de forma privada en el servidor. Ver las fichas no descarga ningún vídeo.
            </p>
          </div>
        </aside>
      )}
    </div>
  );
}
