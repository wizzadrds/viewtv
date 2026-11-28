"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent as ReactKeyboardEvent } from "react";
import Hls from "hls.js";
import DiscoverPanel from "@/components/discover-panel";
import DownloadsPanel from "@/components/downloads-panel";
import RequestsPanel from "@/components/requests-panel";
import StoragePanel from "@/components/storage-panel";
import { apiPath, apiRequest } from "@/lib/api";
import type { CatalogResponse, MediaItem, Profile } from "@/lib/api";

type Session = { id: number; nombre: string };
type View = "loading" | "login" | "catalog" | "discover" | "requests" | "downloads" | "storage";

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
  const [playbackMode, setPlaybackMode] = useState<"direct" | "hls" | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playbackBusy, setPlaybackBusy] = useState(false);
  const [playbackError, setPlaybackError] = useState("");
  const playbackRequest = useRef(0);
  const profileGeneration = useRef(0);
  const pinRef = useRef<HTMLInputElement>(null);

  useSpatialNavigation((view === "catalog" || view === "discover" || view === "login" || view === "requests" || view === "downloads" || view === "storage") && !playbackUrl);

  const loadProfiles = useCallback(async () => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10_000);
    try {
      const data = await apiRequest<{ perfiles: Profile[] }>(
        "/auth/profiles", { signal: controller.signal },
      );
      setProfiles(data.perfiles);
      setLoginError("");
      setView("login");
    } catch {
      setLoginError(
        "La televisión no pudo cargar los perfiles. Pulsa Reintentar o usa la versión Samsung compatible.",
      );
      setView("login");
    } finally {
      window.clearTimeout(timeout);
    }
  }, []);

  const handleSessionExpired = useCallback(() => {
    profileGeneration.current += 1;
    playbackRequest.current += 1;
    setItems([]);
    setTotal(0);
    setProfile(null);
    setSelectedProfile(null);
    setSelectedItem(null);
    setPlaybackUrl(null);
    setPlaybackMode(null);
    setPin("");
    void loadProfiles();
  }, [loadProfiles]);

  const loadCatalog = useCallback(async () => {
    const expectedProfileId = profile?.id;
    if (expectedProfileId === undefined) return;
    const generation = profileGeneration.current;
    setCatalogError("");
    try {
      const query = new URLSearchParams({ perfil_id_esperado: String(expectedProfileId) });
      if (filter !== "todo") query.set("tipo", filter);
      const data = await apiRequest<CatalogResponse>(`/jellyfin/catalog?${query}`);
      if (generation !== profileGeneration.current) return;
      if (data.perfil_id !== expectedProfileId) {
        throw new Error("La sesión ha cambiado de perfil.");
      }
      setItems(data.elementos);
      setTotal(data.total);
    } catch (error) {
      if (generation !== profileGeneration.current) return;
      const status = (error as Error & { status?: number }).status;
      if (status === 401 || status === 409) {
        profileGeneration.current += 1;
        playbackRequest.current += 1;
        setProfile(null);
        setSelectedProfile(null);
        setItems([]);
        setTotal(0);
        setPin("");
        await loadProfiles();
        return;
      }
      setCatalogError((error as Error).message || "No se pudo cargar el catálogo.");
    }
  }, [filter, loadProfiles, profile?.id]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 10_000);
    apiRequest<Session>("/auth/me", { signal: controller.signal })
      .then((session) => {
        if (!active) return;
        setProfile(session);
        setView("discover");
      })
      .catch(() => {
        if (active) void loadProfiles();
      })
      .finally(() => window.clearTimeout(timer));
    return () => {
      active = false;
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [loadProfiles]);

  useEffect(() => {
    if (view === "catalog" && profile) void loadCatalog();
  }, [view, profile, loadCatalog]);

  useEffect(() => {
    if (view !== "catalog" || !profile) return;
    const refreshVisibleCatalog = () => {
      if (document.visibilityState === "visible" && !selectedItem && !playbackUrl) {
        void loadCatalog();
      }
    };
    const interval = window.setInterval(refreshVisibleCatalog, 5 * 60 * 1000);
    document.addEventListener("visibilitychange", refreshVisibleCatalog);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", refreshVisibleCatalog);
    };
  }, [view, profile, selectedItem, playbackUrl, loadCatalog]);

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
      profileGeneration.current += 1;
      playbackRequest.current += 1;
      setItems([]);
      setTotal(0);
      setSelectedItem(null);
      setPlaybackUrl(null);
      setPlaybackMode(null);
      setProfile(result.perfil);
      setPin("");
      setView("discover");
    } catch (error) {
      setLoginError((error as Error).message || "No se ha podido iniciar sesión.");
      setPin("");
      pinRef.current?.focus();
    } finally {
      setBusy(false);
    }
  }

  async function handleLogout() {
    try {
      await apiRequest("/auth/logout", { method: "POST" });
    } finally {
      profileGeneration.current += 1;
      playbackRequest.current += 1;
      setProfile(null);
      setSelectedProfile(null);
      setSelectedItem(null);
      setPlaybackUrl(null);
      setPlaybackMode(null);
      setPin("");
      setItems([]);
      setTotal(0);
      await loadProfiles();
    }
  }

  function closeDetails() {
    playbackRequest.current += 1;
    setPlaybackUrl(null);
    setPlaybackMode(null);
    setPlaybackBusy(false);
    setPlaybackError("");
    setSelectedItem(null);
  }

  function openDetails(item: MediaItem) {
    closeDetails();
    setSelectedItem(item);
  }

  async function handlePlay() {
    if (!selectedItem || playbackBusy || !profile) return;

    const id = selectedItem.id;
    const expectedProfileId = profile.id;
    const requestId = ++playbackRequest.current;
    const generation = profileGeneration.current;
    setPlaybackBusy(true);
    setPlaybackError("");
    setPlaybackUrl(null);
    setPlaybackMode(null);

    try {
      const result = await apiRequest<{
        estado: string;
        fuentes: Array<{
          reproduccion_directa: boolean;
          modo: "direct" | "hls" | null;
          url: string | null;
        }>;
      }>(`/jellyfin/media/${id}/playback-info?perfil_id_esperado=${expectedProfileId}`, {
        method: "POST",
      });

      if (playbackRequest.current !== requestId || generation !== profileGeneration.current) return;

      const direct = result.fuentes.find(
        (item) =>
          item.reproduccion_directa === true
          && item.modo === "direct"
          && typeof item.url === "string"
          && item.url.startsWith(`/jellyfin/media/${id}/stream?`)
      );
      const hls = result.fuentes.find(
        (item) =>
          item.modo === "hls"
          && typeof item.url === "string"
          && item.url.startsWith(`/jellyfin/media/${id}/hls?token=`)
      );
      const source = direct ?? hls;

      if (!source?.url || !source.modo) {
        setPlaybackError("Jellyfin no ofrece una fuente de reproducción compatible.");
        return;
      }

      setPlaybackMode(source.modo);
      setPlaybackUrl(apiPath(source.url));
    } catch (error) {
      if (playbackRequest.current !== requestId || generation !== profileGeneration.current) return;
      setPlaybackError(
        (error as Error).message || "No se pudo iniciar la reproducción."
      );
    } finally {
      if (playbackRequest.current === requestId && generation === profileGeneration.current) {
        setPlaybackBusy(false);
      }
    }
  }

  async function markMovieViewedAfterPlayback() {
    const film = selectedItem;
    const expectedProfileId = profile?.id;
    if (film?.tipo !== "pelicula" || film.visto || expectedProfileId === undefined) return;
    const generation = profileGeneration.current;
    const requestId = playbackRequest.current;
    try {
      // Solo visionado privado del perfil activo. NO solicita retirada.
      await apiRequest(`/almacenamiento/peliculas/${film.id}/visto`, {
        method: "POST",
        body: JSON.stringify({ visto: true, perfil_id_esperado: expectedProfileId }),
      });
      if (generation !== profileGeneration.current || requestId !== playbackRequest.current) return;
      setItems((previous) => previous.map((entry) =>
        entry.id === film.id ? { ...entry, visto: true } : entry));
      setSelectedItem((previous) =>
        previous?.id === film.id ? { ...previous, visto: true } : previous);
    } catch (cause) {
      if (generation !== profileGeneration.current || requestId !== playbackRequest.current) return;
      const status = (cause as Error & { status?: number }).status;
      if (status === 401 || status === 409) {
        handleSessionExpired();
      } else {
        setPlaybackError("La reproducción terminó, pero no se pudo guardar «vista» en este perfil.");
      }
    }
  }

  async function openFromDiscover(mediaId?: number) {
    setView("catalog");
    setFilter("todo");
    if (mediaId === undefined) return;
    try {
      const id = profile?.id;
      if (id === undefined) return;
      const generation = profileGeneration.current;
      const catalog = await apiRequest<CatalogResponse>(`/jellyfin/catalog?limit=100&perfil_id_esperado=${id}`);
      if (generation !== profileGeneration.current || catalog.perfil_id !== id) return;
      const item = catalog.elementos.find((entry) => entry.id === mediaId);
      if (item) openDetails(item);
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 401) {
        handleSessionExpired();
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
    if (!playbackUrl || playbackMode !== "hls" || !videoRef.current) return;
    const video = videoRef.current;
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = playbackUrl;
      void video.play().catch(() => { /* La interacción del usuario puede ser necesaria. */ });
      return () => {
        video.pause();
        video.removeAttribute("src");
        video.load();
      };
    }
    if (!Hls.isSupported()) {
      setPlaybackError("Este navegador no permite reproducir vídeo HLS.");
      return;
    }
    const player = new Hls({ maxBufferLength: 20, backBufferLength: 30 });
    player.attachMedia(video);
    player.on(Hls.Events.MEDIA_ATTACHED, () => player.loadSource(playbackUrl));
    player.on(Hls.Events.ERROR, (_event, data) => {
      if (data.fatal) {
        setPlaybackError(
          "Jellyfin no pudo preparar el vídeo para este navegador. Comprueba la transcodificación."
        );
      }
    });
    return () => {
      player.destroy();
      video.removeAttribute("src");
    };
  }, [playbackUrl, playbackMode]);

  useEffect(() => {
    if (!playbackUrl) return;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setPlaybackUrl(null);
        setPlaybackMode(null);
        setPlaybackError("");
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [playbackUrl]);

  if (view === "loading") {
    return (
      <main className="boot-screen">
        <div className="brand-mark">V</div>
        <p>Iniciando VIEWTV…</p>
        <div className="tv-boot-fallback">
          <span>¿Tu Samsung no avanza de esta pantalla?</span>
          <a href="/tv.html" data-spatial>
            Abrir versión compatible con Samsung
          </a>
        </div>
      </main>
    );
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
          {loginError && (
            <div role="alert">
              <p className="error-message">{loginError}</p>
              <button className="quiet-button" type="button" data-spatial
                onClick={() => { void loadProfiles(); }}>
                Reintentar conexión
              </button>
              <a href="/tv.html" className="quiet-button" data-spatial>
                Abrir versión Samsung compatible
              </a>
            </div>
          )}
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
            className={view === "discover" ? "nav-link nav-active" : "nav-link"}
            data-spatial
            onClick={() => setView("discover")}
            type="button"
            aria-current={view === "discover" ? "page" : undefined}
          >Explorar</button>
          <button
            className={view === "requests" ? "nav-link nav-active" : "nav-link"}
            data-spatial
            onClick={() => setView("requests")}
            type="button"
            aria-current={view === "requests" ? "page" : undefined}
          >Buscar y pedir</button>
          <button
            className={view === "downloads" ? "nav-link nav-active" : "nav-link"}
            data-spatial
            onClick={() => setView("downloads")}
            type="button"
            aria-current={view === "downloads" ? "page" : undefined}
          >Descargas</button>
          <button
            className={view === "storage" ? "nav-link nav-active" : "nav-link"}
            data-spatial
            onClick={() => setView("storage")}
            type="button"
            aria-current={view === "storage" ? "page" : undefined}
          >Espacio</button>
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
          <p className="welcome-copy">Tu colección sigue disponible en todos los perfiles. Solo cambia la marca de «vista» de cada uno.</p>
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
            <span className="muted">Biblioteca actualizada automáticamente</span>
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
            {!search && <p className="muted">La biblioteca se sincroniza sola periódicamente.</p>}
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
              <span className="media-meta">{item.anio ?? "Año desconocido"} · {item.tipo === "pelicula" ? (item.visto ? "Vista en este perfil" : "Sin marcar en este perfil") : "Serie"}</span>
            </button>
          ))}
        </div>
      </section>
        </>
      )}
      {view === "discover" && profile && (
        <DiscoverPanel
          key={profile.id}
          onUnauthorized={handleSessionExpired}
          onShowRequests={() => setView("requests")}
          onShowLibrary={(mediaId) => { void openFromDiscover(mediaId); }}
        />
      )}
      {view === "requests" && profile && (
        <RequestsPanel
          key={profile.id}
          onUnauthorized={handleSessionExpired}
          onShowDownloads={() => setView("downloads")}
        />
      )}
      {view === "downloads" && profile && (
        <DownloadsPanel key={profile.id} onUnauthorized={handleSessionExpired} />
      )}
      {view === "storage" && profile && (
        <StoragePanel key={profile.id} profileId={profile.id} onUnauthorized={handleSessionExpired} />
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
                  {selectedItem.tipo === "pelicula" && (
                    <p className="muted">{selectedItem.visto ? "Vista en tu perfil" : "Pendiente en tu perfil"}. Verla no la retira de otros perfiles ni borra el archivo.</p>
                  )}
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
              ref={videoRef}
              aria-label={`Reproducción de ${selectedItem.titulo}`}
              autoPlay
              className="theater-video"
              controls
              playsInline
              preload="metadata"
              src={playbackMode === "direct" ? playbackUrl : undefined}
              onEnded={() => { void markMovieViewedAfterPlayback(); }}
              onError={() => setPlaybackError("No se pudo reproducir este vídeo en el navegador.")}
            />
          </div>

          <footer className="theater-footer">
            <div className="theater-description">
              <span className="theater-kicker">AHORA REPRODUCIENDO</span>
              <h2 id="theater-title">{selectedItem.titulo}</h2>
              <p>{selectedItem.anio ?? ""} {selectedItem.tipo === "pelicula" ? "· Película" : "· Serie"}</p>
            </div>
            <span className="theater-direct"><span aria-hidden="true" /> {playbackMode === "hls" ? "HLS · JELLYFIN" : "DIRECT PLAY"}</span>
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
