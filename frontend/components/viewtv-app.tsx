"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent as ReactKeyboardEvent } from "react";
import DownloadsPanel from "@/components/downloads-panel";
import { apiPath, apiRequest } from "@/lib/api";
import type { CatalogResponse, MediaItem, Profile } from "@/lib/api";

type Session = { id: number; nombre: string };
type View = "loading" | "login" | "catalog" | "downloads";

function useSpatialNavigation(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) return;
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, select, [contenteditable='true']")) return;

      const current = document.activeElement as HTMLElement | null;
      if (!current?.hasAttribute("data-spatial")) return;

      const currentRect = current.getBoundingClientRect();
      const cx = currentRect.left + currentRect.width / 2;
      const cy = currentRect.top + currentRect.height / 2;
      const candidates = Array.from(document.querySelectorAll<HTMLElement>("[data-spatial]"))
        .filter((element) => element !== current && !element.hasAttribute("disabled"))
        .map((element) => {
          const rect = element.getBoundingClientRect();
          const x = rect.left + rect.width / 2;
          const y = rect.top + rect.height / 2;
          const dx = x - cx;
          const dy = y - cy;
          const primary = event.key === "ArrowLeft" ? -dx
            : event.key === "ArrowRight" ? dx
            : event.key === "ArrowUp" ? -dy : dy;
          const secondary = event.key === "ArrowLeft" || event.key === "ArrowRight"
            ? Math.abs(dy) : Math.abs(dx);
          return { element, primary, secondary, score: primary + secondary * 2.2 };
        })
        .filter((item) => item.primary > 4)
        .sort((a, b) => a.score - b.score);

      if (candidates[0]) {
        event.preventDefault();
        candidates[0].element.focus();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enabled]);
}

export default function ViewTVApp() {
  const [view, setView] = useState<View>("loading");
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profile, setProfile] = useState<Session | null>(null);
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null);
  const [pin, setPin] = useState("");
  const [loginError, setLoginError] = useState("");
  const [items, setItems] = useState<MediaItem[]>([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState<"todo" | "pelicula" | "serie">("todo");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [catalogError, setCatalogError] = useState("");
  const [selectedItem, setSelectedItem] = useState<MediaItem | null>(null);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [playbackBusy, setPlaybackBusy] = useState(false);
  const [playbackError, setPlaybackError] = useState("");
  const playbackRequest = useRef(0);
  const pinRef = useRef<HTMLInputElement>(null);

  useSpatialNavigation((view === "catalog" || view === "login" || view === "downloads") && !playbackUrl);

  const loadProfiles = useCallback(async () => {
    try {
      const data = await apiRequest<{ perfiles: Profile[] }>("/auth/profiles");
      setProfiles(data.perfiles);
      setView("login");
    } catch {
      setLoginError("No se puede conectar con VIEWTV. Comprueba que el servidor esté encendido.");
      setView("login");
    }
  }, []);

  const handleSessionExpired = useCallback(() => {
    setProfile(null);
    setSelectedProfile(null);
    setSelectedItem(null);
    setPlaybackUrl(null);
    setPin("");
    void loadProfiles();
  }, [loadProfiles]);

  const loadCatalog = useCallback(async () => {
    setCatalogError("");
    try {
      const query = filter === "todo" ? "" : `?tipo=${filter}`;
      const data = await apiRequest<CatalogResponse>(`/jellyfin/catalog${query}`);
      setItems(data.elementos);
      setTotal(data.total);
    } catch (error) {
      if ((error as Error & { status?: number }).status === 401) {
        setProfile(null);
        setSelectedProfile(null);
        setPin("");
        await loadProfiles();
        return;
      }
      setCatalogError((error as Error).message || "No se pudo cargar el catálogo.");
    }
  }, [filter, loadProfiles]);

  useEffect(() => {
    let active = true;
    apiRequest<Session>("/auth/me")
      .then((session) => {
        if (!active) return;
        setProfile(session);
        setView("catalog");
      })
      .catch(() => {
        if (active) void loadProfiles();
      });
    return () => { active = false; };
  }, [loadProfiles]);

  useEffect(() => {
    if (view === "catalog" && profile) void loadCatalog();
  }, [view, profile, loadCatalog]);

  useEffect(() => {
    if (selectedProfile) pinRef.current?.focus();
  }, [selectedProfile]);

  const visibleItems = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("es-ES");
    if (!term) return items;
    return items.filter((item) =>
      item.titulo.toLocaleLowerCase("es-ES").includes(term)
      || item.generos.some((genre) => genre.toLocaleLowerCase("es-ES").includes(term)),
    );
  }, [items, search]);

  const selectedPoster = selectedItem?.imagen_portada ?? selectedItem?.imagen_fondo;

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProfile || !/^\d{4,8}$/.test(pin)) {
      setLoginError("Introduce un PIN de entre 4 y 8 dígitos.");
      return;
    }
    setBusy(true);
    setLoginError("");
    try {
      const result = await apiRequest<{ estado: string; perfil: Session }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ nombre: selectedProfile.nombre, pin }),
      });
      setProfile(result.perfil);
      setPin("");
      setView("catalog");
    } catch (error) {
      setLoginError((error as Error).message || "No se ha podido iniciar sesión.");
      setPin("");
      pinRef.current?.focus();
    } finally {
      setBusy(false);
    }
  }

  async function handleSync() {
    setBusy(true);
    setCatalogError("");
    try {
      await apiRequest("/jellyfin/catalog/sync", { method: "POST" });
      await loadCatalog();
    } catch (error) {
      setCatalogError((error as Error).message || "No se pudo sincronizar Jellyfin.");
    } finally {
      setBusy(false);
    }
  }

  async function handleLogout() {
    try {
      await apiRequest("/auth/logout", { method: "POST" });
    } finally {
      setProfile(null);
      setSelectedProfile(null);
      setPin("");
      setItems([]);
      await loadProfiles();
    }
  }

  function closeDetails() {
    playbackRequest.current += 1;
    setPlaybackUrl(null);
    setPlaybackBusy(false);
    setPlaybackError("");
    setSelectedItem(null);
  }

  function openDetails(item: MediaItem) {
    closeDetails();
    setSelectedItem(item);
  }

  async function handlePlay() {
    if (!selectedItem || playbackBusy) return;

    const id = selectedItem.id;
    const requestId = ++playbackRequest.current;
    setPlaybackBusy(true);
    setPlaybackError("");
    setPlaybackUrl(null);

    try {
      const result = await apiRequest<{
        estado: string;
        fuentes: Array<{
          reproduccion_directa: boolean;
          url: string | null;
        }>;
      }>(`/jellyfin/media/${id}/playback-info`, {
        method: "POST",
      });

      if (playbackRequest.current !== requestId) return;

      const source = result.fuentes.find(
        (item) =>
          item.reproduccion_directa === true
          && typeof item.url === "string"
          && item.url.startsWith(`/jellyfin/media/${id}/stream?`)
      );

      if (!source?.url) {
        setPlaybackError("No hay una fuente Direct Play disponible.");
        return;
      }

      setPlaybackUrl(apiPath(source.url));
    } catch (error) {
      if (playbackRequest.current !== requestId) return;
      setPlaybackError(
        (error as Error).message || "No se pudo iniciar la reproducción."
      );
    } finally {
      if (playbackRequest.current === requestId) {
        setPlaybackBusy(false);
      }
    }
  }

  function onPinKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      const form = event.currentTarget.form;
      form?.requestSubmit();
    }
  }

  useEffect(() => {
    if (!selectedItem) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [selectedItem]);

  useEffect(() => {
    if (!playbackUrl) return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setPlaybackUrl(null);
        setPlaybackError("");
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [playbackUrl]);

  if (view === "loading") {
    return <main className="boot-screen"><div className="brand-mark">V</div><p>Iniciando VIEWTV…</p></main>;
  }

  if (view === "login") {
    return (
      <main className="login-screen">
        <div className="login-brand"><span className="brand-mark">V</span><span>VIEWTV</span></div>
        <section className="login-panel" aria-labelledby="login-title">
          <p className="eyebrow">TU CINE EN CASA</p>
          <h1 id="login-title">¿Quién está viendo?</h1>
          <div className="profile-list">
            {profiles.map((item) => (
              <button
                className={`profile-choice ${selectedProfile?.id === item.id ? "selected" : ""}`}
                data-spatial
                key={item.id}
                onClick={() => { setSelectedProfile(item); setPin(""); setLoginError(""); }}
                type="button"
              >
                <span className="profile-avatar">{item.nombre.slice(0, 1).toLocaleUpperCase("es-ES")}</span>
                <span>{item.nombre}</span>
              </button>
            ))}
          </div>
          {profiles.length === 0 && <p className="muted">No hay perfiles activos disponibles.</p>}
          {selectedProfile && (
            <form className="pin-form" onSubmit={handleLogin}>
              <label htmlFor="pin">PIN de {selectedProfile.nombre}</label>
              <input
                ref={pinRef}
                id="pin"
                autoComplete="current-password"
                inputMode="numeric"
                maxLength={8}
                onChange={(event) => setPin(event.target.value.replace(/\D/g, "").slice(0, 8))}
                onKeyDown={onPinKeyDown}
                placeholder="Introduce tu PIN"
                type="password"
                value={pin}
              />
              <button className="primary-button" disabled={busy || !/^\d{4,8}$/.test(pin)} type="submit">
                {busy ? "Entrando…" : "Entrar"}
              </button>
            </form>
          )}
          {loginError && <p className="error-message" role="alert">{loginError}</p>}
        </section>
        <p className="login-footer">Biblioteca multimedia privada · Red local</p>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="wordmark"><span className="brand-mark small">V</span><span>VIEWTV</span></div>
        <nav className="main-nav" aria-label="Secciones">
          <button
            className={view === "catalog" ? "nav-link nav-active" : "nav-link"}
            data-spatial
            onClick={() => setView("catalog")}
            type="button"
            aria-current={view === "catalog" ? "page" : undefined}
          >Biblioteca</button>
          <button
            className={view === "downloads" ? "nav-link nav-active" : "nav-link"}
            data-spatial
            onClick={() => setView("downloads")}
            type="button"
            aria-current={view === "downloads" ? "page" : undefined}
          >Descargas</button>
        </nav>
        <div className="account-actions">
          <span className="profile-label">{profile?.nombre}</span>
          <button className="quiet-button" data-spatial onClick={handleLogout} type="button">Salir</button>
        </div>
      </header>

      {view === "catalog" && (
        <>
      <section className="welcome-block">
        <div>
          <p className="eyebrow">TU BIBLIOTECA PERSONAL</p>
          <h1>Todo lo que te gusta,<br /><span>en un solo lugar.</span></h1>
          <p className="welcome-copy">Tu colección, lista para disfrutar.</p>
        </div>
        <div className="server-status"><span className="status-dot" /> Catálogo de tu biblioteca</div>
      </section>

      <section className="catalog-section" aria-labelledby="catalog-title">
        <div className="section-heading">
          <div><p className="eyebrow">EXPLORA TU COLECCIÓN</p><h2 id="catalog-title">Mi biblioteca <span className="count">{total}</span></h2></div>
          <div className="catalog-tools">
            <label className="search-box">
              <span aria-hidden="true">⌕</span>
              <input aria-label="Buscar en la biblioteca" onChange={(event) => setSearch(event.target.value)} placeholder="Buscar títulos o géneros" value={search} />
            </label>
            <button className="quiet-button" data-spatial disabled={busy} onClick={handleSync} type="button">
              {busy ? "Actualizando…" : "↻ Sincronizar"}
            </button>
          </div>
        </div>
        <div className="filter-row" aria-label="Filtrar biblioteca">
          {([
            ["todo", "Todo"],
            ["pelicula", "Películas"],
            ["serie", "Series"],
          ] as const).map(([value, label]) => (
            <button className={filter === value ? "filter-chip active" : "filter-chip"} data-spatial key={value} onClick={() => setFilter(value)} type="button">{label}</button>
          ))}
        </div>

        {catalogError && <p className="error-message catalog-error" role="alert">{catalogError}</p>}
        {busy && items.length === 0 && <p className="muted">Cargando biblioteca…</p>}
        {!catalogError && !busy && visibleItems.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">▧</div>
            <h3>{search ? "No encontramos ese título" : "Tu biblioteca está esperando"}</h3>
            <p>{search ? "Prueba con otro nombre o género." : "Cuando añadas contenido a Jellyfin, aparecerá aquí con sus carátulas y detalles."}</p>
            {!search && <button className="primary-button compact" data-spatial onClick={handleSync} type="button">Actualizar biblioteca</button>}
          </div>
        )}

        <div className="media-grid">
          {visibleItems.map((item) => (
            <button className="media-card" data-spatial key={item.id} onClick={() => openDetails(item)} type="button">
              <span className="poster-wrap">
                {item.imagen_portada ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img alt="" className="poster-image" loading="lazy" src={apiPath(item.imagen_fondo || item.imagen_portada)} />
                ) : <span className="poster-placeholder">VIEWTV</span>}
                <span className="poster-overlay"><span>Ver detalles</span></span>
              </span>
              <span className="media-title">{item.titulo}</span>
              <span className="media-meta">{item.anio ?? "Año desconocido"} · {item.tipo === "pelicula" ? "Película" : "Serie"}</span>
            </button>
          ))}
        </div>
      </section>
        </>
      )}
      {view === "downloads" && profile && (
        <DownloadsPanel key={profile.id} onUnauthorized={handleSessionExpired} />
      )}

      {selectedItem && !playbackUrl && (
        <div className="dialog-backdrop" role="presentation" onClick={closeDetails}>
          <section aria-labelledby="detail-title" aria-modal="true" className="detail-dialog" onClick={(event) => event.stopPropagation()} role="dialog">
            <button aria-label="Cerrar detalles" className="dialog-close" data-spatial onClick={closeDetails} type="button">×</button>
            {selectedItem.imagen_fondo && (
              // eslint-disable-next-line @next/next/no-img-element
              <img alt="" className="detail-backdrop" src={apiPath(selectedItem.imagen_fondo)} />
            )}
            <div className="detail-content">
              <div className={selectedPoster ? "detail-layout has-poster" : "detail-layout"}>
                {selectedPoster && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    alt={`Imagen de ${selectedItem.titulo}`}
                    className="detail-poster"
                    src={apiPath(selectedPoster)}
                  />
                )}
                <div className="detail-copy">
                  <p className="eyebrow">{selectedItem.tipo === "pelicula" ? "PELÍCULA" : "SERIE"}</p>
                  <h2 id="detail-title">{selectedItem.titulo}</h2>
                  <p className="detail-meta">{selectedItem.anio ?? "Año desconocido"}{selectedItem.generos.length ? ` · ${selectedItem.generos.join(" · ")}` : ""}</p>
                  <p className="detail-synopsis">{selectedItem.sinopsis || "No hay sinopsis disponible para este título."}</p>
                  {!playbackUrl && (
                    <button
                      className="primary-button compact"
                      data-spatial
                      disabled={playbackBusy}
                      onClick={handlePlay}
                      type="button"
                    >
                      {playbackBusy ? "Preparando vídeo…" : "Reproducir"}
                    </button>
                  )}
                  {playbackError && (
                    <p className="error-message" role="alert">
                      {playbackError}
                    </p>
                  )}
                  <button className="quiet-button" data-spatial onClick={closeDetails} type="button">Volver a la biblioteca</button>
                </div>
              </div>
            </div>
          </section>
        </div>
      )}
      {selectedItem && playbackUrl && (
        <section className="theater-screen" role="dialog" aria-modal="true" aria-labelledby="theater-title">
          <header className="theater-header">
            <button
              autoFocus
              className="theater-back"
              data-spatial
              onClick={() => { setPlaybackUrl(null); setPlaybackError(""); }}
              type="button"
            >
              <span aria-hidden="true">←</span> Volver a la ficha
            </button>
            <div className="theater-brand" aria-label="VIEWTV Cine">
              <span className="theater-brand-mark">V</span>
              <span>VIEWTV</span>
              <span className="theater-brand-label">CINE</span>
            </div>
          </header>

          <div className="theater-stage">
            <video
              aria-label={`Reproducción de ${selectedItem.titulo}`}
              autoPlay
              className="theater-video"
              controls
              playsInline
              preload="metadata"
              src={playbackUrl}
              onError={() => setPlaybackError("No se pudo reproducir este vídeo en el navegador.")}
            />
          </div>

          <footer className="theater-footer">
            <div className="theater-description">
              <span className="theater-kicker">AHORA REPRODUCIENDO</span>
              <h2 id="theater-title">{selectedItem.titulo}</h2>
              <p>{selectedItem.anio ?? ""} {selectedItem.tipo === "pelicula" ? "· Película" : "· Serie"}</p>
            </div>
            <span className="theater-direct"><span aria-hidden="true" /> DIRECT PLAY</span>
          </footer>

          {playbackError && (
            <div className="theater-error" role="alert">
              <p>{playbackError}</p>
              <button className="theater-back" onClick={() => { setPlaybackUrl(null); setPlaybackError(""); }} type="button">
                Volver a la ficha
              </button>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
