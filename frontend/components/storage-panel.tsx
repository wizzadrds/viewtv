"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

type Usage = { bytes: number; archivos: number; completo: boolean };
type Summary = {
  disco: { total_bytes: number; libre_bytes: number; ocupado_en_volumen_bytes: number } | null;
  peliculas: Usage;
  descargas_temporales: Usage;
  cache_temporal: Usage;
  cache_gestionada: boolean;
  cache_cuota_configurada_bytes: number;
  cache_cuota_aplicada: boolean;
  catalogo_tmdb_bytes: number | null;
  aviso: string;
};
type Film = {
  id: number;
  titulo: string;
  anio: number | null;
  visto: boolean;
  vista_en: string | null;
  solicitud_retirada: string | null;
  eliminacion_automatica_disponible: boolean;
};
type FilmList = { elementos: Film[]; total: number; limit: number; offset: number };
const PAGE_SIZE = 20;

function size(bytes: number | null): string {
  if (bytes === null) return "No disponible";
  if (bytes === 0) return "0 B";
  const unit = bytes >= 1024 ** 3 ? "GiB" : bytes >= 1024 ** 2 ? "MiB" : "KiB";
  const divisor = unit === "GiB" ? 1024 ** 3 : unit === "MiB" ? 1024 ** 2 : 1024;
  return `${new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }).format(bytes / divisor)} ${unit}`;
}

export default function StoragePanel({ onUnauthorized }: { onUnauthorized: () => void }) {
  const [data, setData] = useState<Summary | null>(null);
  const [films, setFilms] = useState<FilmList | null>(null);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [onlyWatched, setOnlyWatched] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    Promise.all([
      apiRequest<Summary>("/almacenamiento/resumen", { signal: controller.signal }),
      apiRequest<FilmList>(
        `/almacenamiento/peliculas?limit=${PAGE_SIZE}&offset=${offset}`,
        { signal: controller.signal },
      ),
    ]).then(([summary, listing]) => {
      if (controller.signal.aborted) return;
      setData(summary);
      setFilms(listing);
      setError("");
    }).catch((cause) => {
      if (controller.signal.aborted) return;
      if ((cause as Error & { status?: number }).status === 401) {
        onUnauthorized();
        return;
      }
      setError((cause as Error).message || "No se pudo consultar el almacenamiento.");
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [offset, onUnauthorized, reload]);

  async function changeViewed(film: Film) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiRequest(`/almacenamiento/peliculas/${film.id}/visto`, {
        method: "POST",
        body: JSON.stringify({ visto: !film.visto }),
      });
      setNotice(film.visto ? "Película desmarcada como vista." : "Marcada como vista en tu perfil.");
      setReload((value) => value + 1);
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) onUnauthorized();
      else setError((cause as Error).message || "No se pudo guardar el cambio.");
    } finally {
      setBusy(false);
    }
  }

  async function requestRemoval(film: Film) {
    if (busy || !film.visto) return;
    const typed = window.prompt(
      "Para registrar una solicitud de retirada, escribe exactamente el título. " +
      "Ningún archivo se borrará ahora: los hardlinks NTFS y qBittorrent requieren revisión.",
      "",
    );
    if (typed === null) return;
    if (typed !== film.titulo) {
      setError("El título no coincide. No se ha registrado ninguna solicitud.");
      return;
    }
    if (!window.confirm(
      `¿Registrar la retirada de «${film.titulo}» para revisión? NO se eliminarán archivos todavía.`,
    )) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await apiRequest<{ mensaje: string }>(
        `/almacenamiento/peliculas/${film.id}/retirada`,
        { method: "POST", body: JSON.stringify({ titulo: typed }) },
      );
      setNotice(result.mensaje);
      setReload((value) => value + 1);
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) onUnauthorized();
      else setError((cause as Error).message || "No se registró la petición.");
    } finally {
      setBusy(false);
    }
  }

  async function cancelRemoval(film: Film) {
    if (busy || !window.confirm(`¿Cancelar la retirada pendiente de «${film.titulo}»?`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiRequest(`/almacenamiento/peliculas/${film.id}/retirada`, {
        method: "DELETE",
      });
      setNotice("Retirada cancelada. La película sigue en la biblioteca.");
      setReload((value) => value + 1);
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) onUnauthorized();
      else setError((cause as Error).message || "No se pudo cancelar.");
    } finally {
      setBusy(false);
    }
  }

  async function clearCache() {
    if (busy || !data?.cache_gestionada) return;
    if (!window.confirm(
      "¿Eliminar solo archivos temporales propios, identificados y sin enlaces duros? " +
      "Nunca borra películas, torrents, metadatos TMDB ni la caché de Jellyfin.",
    )) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await apiRequest<{ archivos: number; bytes: number }>(
        "/almacenamiento/cache/limpiar",
        { method: "POST", body: JSON.stringify({ confirmacion: "LIMPIAR TEMPORALES" }) },
      );
      setNotice(`Limpieza terminada: ${result.archivos} archivos temporales; ${size(result.bytes)}.`);
      setReload((value) => value + 1);
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) onUnauthorized();
      else setError((cause as Error).message || "No se pudo limpiar.");
    } finally {
      setBusy(false);
    }
  }

  const visible = (films?.elementos ?? []).filter((film) => {
    const matchesSearch = film.titulo.toLocaleLowerCase("es-ES")
      .includes(search.toLocaleLowerCase("es-ES").trim());
    return matchesSearch && (!onlyWatched || film.visto);
  });

  return (
    <section className="storage-section" aria-labelledby="storage-title">
      <header className="storage-heading">
        <p className="eyebrow">BIBLIOTECA Y ESPACIO</p>
        <h1 id="storage-title">Gestiona tu almacenamiento</h1>
        <p className="welcome-copy">
          Comprueba el espacio, marca películas vistas y prepara retiradas seguras sin tocar otras descargas.
        </p>
      </header>
      {error && <p className="error-message" role="alert">{error}</p>}
      {notice && <p className="storage-notice" role="status">{notice}</p>}
      {loading && <p className="muted">Consultando espacio y biblioteca…</p>}
      {data && (
        <>
          <div className="storage-stats">
            <div className="storage-metric">
              <span>Espacio libre en el disco</span>
              <strong>{size(data.disco?.libre_bytes ?? null)}</strong>
              <small>Incluye otros programas y archivos del volumen.</small>
            </div>
            <div className="storage-metric">
              <span>Biblioteca de películas</span>
              <strong>{size(data.peliculas.bytes)}</strong>
              <small>{data.peliculas.archivos} archivos · {data.peliculas.completo ? "Lectura completa" : "Lectura parcial"} · tamaño lógico.</small>
            </div>
            <div className="storage-metric">
              <span>Descargas temporales</span>
              <strong>{size(data.descargas_temporales.bytes)}</strong>
              <small>Nunca se limpian automáticamente desde aquí.</small>
            </div>
            <div className="storage-metric">
              <span>Caché local de ViewTV</span>
              <strong>{size(data.cache_temporal.bytes)}</strong>
              <small>Cuota configurada {size(data.cache_cuota_configurada_bytes)}; todavía no se aplica a todos los programas.</small>
            </div>
          </div>
          <div className="storage-cache-actions">
            <div>
              <h2>Temporales y metadatos</h2>
              <p>Las fichas TMDB ocupan {size(data.catalogo_tmdb_bytes)} y caducan de forma independiente. Jellyfin y sus transcodificaciones se conservan.</p>
            </div>
            <button className="quiet-button" data-spatial disabled={busy || !data.cache_gestionada}
              type="button" onClick={() => void clearCache()}>
              Limpiar temporales propios
            </button>
          </div>
          <p className="storage-warning">{data.aviso}</p>
          {!data.cache_gestionada && <p className="muted">No hay caché temporal gestionada que limpiar.</p>}
        </>
      )}
      <div className="storage-list-heading">
        <div>
          <h2>Películas de tu biblioteca</h2>
          <p className="muted">
            Marcar «vista» es manual y exclusivo de este perfil. La retirada queda pendiente
            hasta comprobar la propiedad de los archivos en Windows; no los borra todavía.
          </p>
        </div>
        <div className="storage-filters">
          <input aria-label="Buscar película en esta página" value={search}
            onChange={(event) => setSearch(event.target.value)} placeholder="Buscar en esta página…" />
          <label><input type="checkbox" checked={onlyWatched}
            onChange={(event) => setOnlyWatched(event.target.checked)} /> Solo vistas</label>
        </div>
      </div>
      <div className="storage-film-list">
        {visible.map((film) => (
          <article className="storage-film" key={film.id}>
            <div className="storage-film-info">
              <strong>{film.titulo}</strong>
              <span>{film.anio ?? "Año desconocido"} · {film.visto ? "Vista en tu perfil" : "Sin marcar como vista"}</span>
              {film.solicitud_retirada === "pendiente_revision" && (
                <span className="storage-pending">Retirada pendiente de revisión · archivo intacto</span>
              )}
            </div>
            <div className="storage-film-actions">
              <button className="quiet-button" data-spatial type="button" disabled={busy}
                onClick={() => void changeViewed(film)}>
                {film.visto ? "Quitar «vista»" : "Marcar como vista"}
              </button>
              {film.solicitud_retirada === "pendiente_revision" ? (
                <button className="quiet-button" data-spatial type="button" disabled={busy}
                  onClick={() => void cancelRemoval(film)}>Cancelar retirada</button>
              ) : (
                <button className="storage-remove-action" data-spatial type="button"
                  disabled={busy || !film.visto} onClick={() => void requestRemoval(film)}>
                  Solicitar retirada
                </button>
              )}
            </div>
          </article>
        ))}
        {!loading && visible.length === 0 && (
          <p className="muted">No hay películas que coincidan en esta página.</p>
        )}
      </div>
      <nav className="storage-pagination" aria-label="Páginas de películas">
        <button className="quiet-button" data-spatial type="button" disabled={busy || offset <= 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</button>
        <span>Películas {films?.total ? offset + 1 : 0}–{Math.min(offset + PAGE_SIZE, films?.total ?? 0)} de {films?.total ?? 0}</span>
        <button className="quiet-button" data-spatial type="button"
          disabled={busy || offset + PAGE_SIZE >= (films?.total ?? 0)}
          onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</button>
      </nav>
    </section>
  );
}
