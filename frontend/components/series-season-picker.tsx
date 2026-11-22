"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export type SeasonSummary = {
  temporada: number;
  titulo: string;
  numero_episodios: number;
  imagen_portada: string | null;
  fecha_estreno: string | null;
};

type Episode = {
  episodio: number;
  temporada: number;
  titulo: string;
  sinopsis: string | null;
  imagen: string | null;
  fecha_emision: string | null;
  duracion_minutos: number | null;
  solicitable: boolean;
};

type SeasonPage = {
  tmdb_id: number;
  titulo_serie: string;
  temporada: number;
  titulo_temporada: string;
  sinopsis_temporada: string | null;
  episodios: Episode[];
  total: number;
  pagina: number;
  paginas: number;
  disponible_local: boolean;
  aviso_disponibilidad: string | null;
};

function safeImage(source: string | null): string | null {
  return source?.startsWith("https://image.tmdb.org/t/p/") ? source : null;
}

function dateLabel(source: string | null): string | null {
  if (!source || !/^\d{4}-\d{2}-\d{2}$/.test(source)) return null;
  const parsed = new Date(source + "T12:00:00Z");
  return Number.isNaN(parsed.getTime()) ? null : parsed.toLocaleDateString("es-ES", {
    day: "numeric", month: "short", year: "numeric",
    timeZone: "UTC",
  });
}

export default function SeriesSeasonPicker({
  seriesId,
  seasons,
  onUnauthorized,
  onShowRequests,
}: {
  seriesId: number;
  seasons: SeasonSummary[];
  onUnauthorized: () => void;
  onShowRequests: () => void;
}) {
  const [season, setSeason] = useState<number>(() =>
    seasons.find((item) => item.temporada > 0)?.temporada ?? seasons[0]?.temporada ?? 0,
  );
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<SeasonPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [requesting, setRequesting] = useState<number | null>(null);
  const [requested, setRequested] = useState<string[]>([]);

  useEffect(() => {
    if (!seasons.some((item) => item.temporada === season)) return;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    const url = "/descubrir/serie/" + seriesId + "/temporadas/" + season
      + "?pagina=" + page;
    void apiRequest<SeasonPage>(url, { signal: controller.signal })
      .then((response) => {
        if (controller.signal.aborted) return;
        setResult((previous) => {
          if (page === 1 || !previous || previous.temporada !== season) return response;
          const existing = new Set(previous.episodios.map((episode) => episode.episodio));
          return {
            ...response,
            episodios: [
              ...previous.episodios,
              ...response.episodios.filter((episode) => !existing.has(episode.episodio)),
            ],
          };
        });
      })
      .catch((cause) => {
        if (controller.signal.aborted) return;
        if ((cause as Error & { status?: number }).status === 401) onUnauthorized();
        else setError((cause as Error).message || "No se pudo cargar esta temporada.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [seriesId, season, page, seasons, onUnauthorized]);

  const chooseSeason = (number: number) => {
    if (number === season) return;
    setSeason(number);
    setPage(1);
    setResult(null);
    setNotice("");
    setError("");
  };

  const requestEpisode = async (episode: Episode) => {
    if (requesting !== null || !episode.solicitable) return;
    setRequesting(episode.episodio);
    setNotice("");
    const episodeCode = "S" + String(season).padStart(2, "0")
      + "E" + String(episode.episodio).padStart(2, "0");
    try {
      await apiRequest(
        "/descubrir/serie/" + seriesId + "/temporadas/" + season
        + "/episodios/" + episode.episodio + "/solicitar",
        { method: "POST" },
      );
      setRequested((previous) => [...previous, season + ":" + episode.episodio]);
      setNotice("Solicitud " + episodeCode + " creada. Todavía no se ha descargado nada.");
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) {
        onUnauthorized();
        return;
      }
      setNotice((cause as Error).message || "No se pudo crear la solicitud.");
    } finally {
      setRequesting(null);
    }
  };

  if (!seasons.length) {
    return (
      <div className="series-season-panel">
        <h3>Temporadas y episodios</h3>
        <p className="muted">TMDB todavía no ofrece una lista de temporadas para esta serie.</p>
      </div>
    );
  }

  return (
    <section className="series-season-panel" aria-label="Temporadas y episodios">
      <div className="series-season-intro">
        <div>
          <p className="eyebrow">TU SERIE, CAPÍTULO A CAPÍTULO</p>
          <h3>Temporadas y episodios</h3>
          <p className="muted">Elige únicamente el episodio que quieres solicitar.</p>
        </div>
        <span className="series-season-total">{seasons.length} temporadas</span>
      </div>
      <div className="series-season-tabs" aria-label="Seleccionar temporada" role="group">
        {seasons.map((entry) => (
          <button
            key={entry.temporada}
            type="button"
            data-spatial
            className={entry.temporada === season ? "series-season-chip selected" : "series-season-chip"}
            aria-pressed={entry.temporada === season}
            onClick={() => chooseSeason(entry.temporada)}
          >
            <strong>{entry.temporada === 0 ? "Especiales" : "Temporada " + entry.temporada}</strong>
            <span>{entry.numero_episodios} episodios</span>
          </button>
        ))}
      </div>

      {result && result.temporada === season && (
        <div className="series-season-description">
          <strong>{result.titulo_temporada}</strong>
          <span>{result.total} capítulos</span>
          {result.sinopsis_temporada && <p>{result.sinopsis_temporada}</p>}
          {result.aviso_disponibilidad && (
            <p className="series-local-warning">{result.aviso_disponibilidad}</p>
          )}
        </div>
      )}

      {error && <p className="error-message" role="alert">{error}</p>}
      {loading && <p className="muted" role="status">Preparando episodios de la temporada…</p>}
      {!loading && !error && result?.temporada === season && result.total === 0 && (
        <p className="muted">Todavía no hay episodios publicados para esta temporada.</p>
      )}

      {result?.temporada === season && result.episodios.length > 0 && (
        <div className="series-episode-list">
          {result.episodios.map((episode) => {
            const key = season + ":" + episode.episodio;
            const alreadyRequested = requested.includes(key);
            const picture = safeImage(episode.imagen);
            const date = dateLabel(episode.fecha_emision);
            return (
              <article className="series-episode" key={episode.episodio}>
                <div className="series-episode-picture" aria-hidden="true">
                  {picture ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={picture} alt="" loading="lazy" />
                  ) : (
                    <span>VIEWTV</span>
                  )}
                </div>
                <div className="series-episode-info">
                  <div className="series-episode-top">
                    <span className="series-episode-number">
                      {season === 0 ? "Especial " : "Episodio "}{episode.episodio}
                    </span>
                    <span className="series-episode-meta">
                      {[date, episode.duracion_minutos ? episode.duracion_minutos + " min" : null]
                        .filter(Boolean).join(" · ")}
                    </span>
                  </div>
                  <h4>{episode.titulo}</h4>
                  <p className="series-episode-synopsis">
                    {episode.sinopsis || "Sin sinopsis disponible para este capítulo."}
                  </p>
                  <div className="series-episode-actions">
                    <button
                      type="button"
                      data-spatial
                      className={alreadyRequested ? "quiet-button" : "series-episode-request"}
                      disabled={!episode.solicitable || requesting !== null || alreadyRequested}
                      onClick={() => { void requestEpisode(episode); }}
                      aria-label={"Solicitar " + episode.titulo + ", temporada " + season
                        + ", episodio " + episode.episodio}
                    >
                      {!episode.solicitable
                        ? "Próximamente"
                        : alreadyRequested
                          ? "Solicitado"
                          : requesting === episode.episodio
                            ? "Solicitando…"
                            : "Solicitar episodio"}
                    </button>
                    {!episode.fecha_emision && (
                      <span className="muted series-episode-date-note">Estreno no confirmado</span>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {!loading && !error && result?.temporada === season && page < result.paginas && (
        <div className="series-load-more">
          <button
            type="button" data-spatial className="quiet-button"
            onClick={() => setPage((previous) => previous + 1)}
          >
            Ver más episodios
          </button>
          <span className="muted">{result.episodios.length} de {result.total}</span>
        </div>
      )}

      {notice && (
        <div className="discover-notice" role="status" aria-live="polite">
          <p>{notice}</p>
          {notice.startsWith("Solicitud") && (
            <button className="quiet-button" type="button" data-spatial onClick={onShowRequests}>
              Ir a «Buscar y pedir» para elegir una fuente
            </button>
          )}
        </div>
      )}
      <p className="series-season-footnote">
        Una solicitud no inicia la descarga. Solo podrás elegir una fuente autorizada
        después de crearla. Que un episodio aparezca aquí no garantiza que exista
        un archivo disponible.
      </p>
    </section>
  );
}
