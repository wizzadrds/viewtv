"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { apiPath, apiRequest } from "@/lib/api";
import type { CatalogResponse, MediaItem, Profile } from "@/lib/api";

type Session = { id: number; nombre: string };
type View = "loading" | "login" | "catalog";

function useSpatialNavigation(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;

    const onKeyDown = (event: globalThis.KeyboardEvent) => {
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
  const pinRef = useRef<HTMLInputElement>(null);

  useSpatialNavigation(view === "catalog" || view === "login");

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

  function onPinKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      const form = event.currentTarget.form;
      form?.requestSubmit();
    }
  }

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
          <span className="nav-active">Inicio</span>
          <span>Películas y series</span>
        </nav>
        <div className="account-actions">
          <span className="profile-label">{profile?.nombre}</span>
          <button className="quiet-button" data-spatial onClick={handleLogout} type="button">Salir</button>
        </div>
      </header>

      <section className="welcome-block">
        <div>
          <p className="eyebrow">TU BIBLIOTECA PERSONAL</p>
          <h1>Todo lo que te gusta,<br /><span>en un solo lugar.</span></h1>
          <p className="welcome-copy">Tu colección, lista para disfrutar.</p>
        </div>
        <div className="server-status"><span className="status-dot" /> Biblioteca conectada a VIEWTV</div>
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
            <button className="media-card" data-spatial key={item.id} onClick={() => setSelectedItem(item)} type="button">
              <span className="poster-wrap">
                {item.imagen_portada ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img alt="" className="poster-image" loading="lazy" src={apiPath(item.imagen_portada)} />
                ) : <span className="poster-placeholder">VIEWTV</span>}
                <span className="poster-overlay"><span>Ver detalles</span></span>
              </span>
              <span className="media-title">{item.titulo}</span>
              <span className="media-meta">{item.anio ?? "Año desconocido"} · {item.tipo === "pelicula" ? "Película" : "Serie"}</span>
            </button>
          ))}
        </div>
      </section>

      {selectedItem && (
        <div className="dialog-backdrop" role="presentation" onClick={() => setSelectedItem(null)}>
          <section aria-labelledby="detail-title" aria-modal="true" className="detail-dialog" onClick={(event) => event.stopPropagation()} role="dialog">
            <button aria-label="Cerrar detalles" className="dialog-close" data-spatial onClick={() => setSelectedItem(null)} type="button">×</button>
            {selectedItem.imagen_fondo && (
              // eslint-disable-next-line @next/next/no-img-element
              <img alt="" className="detail-backdrop" src={apiPath(selectedItem.imagen_fondo)} />
            )}
            <div className="detail-content">
              <p className="eyebrow">{selectedItem.tipo === "pelicula" ? "PELÍCULA" : "SERIE"}</p>
              <h2 id="detail-title">{selectedItem.titulo}</h2>
              <p className="detail-meta">{selectedItem.anio ?? "Año desconocido"}{selectedItem.generos.length ? ` · ${selectedItem.generos.join(" · ")}` : ""}</p>
              <p className="detail-synopsis">{selectedItem.sinopsis || "No hay sinopsis disponible para este título."}</p>
              <p className="muted small-note">La reproducción se integrará en la siguiente etapa.</p>
              <button className="primary-button compact" data-spatial onClick={() => setSelectedItem(null)} type="button">Volver a la biblioteca</button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
