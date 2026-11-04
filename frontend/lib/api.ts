export type Profile = { id: number; nombre: string };

export type MediaItem = {
  id: number;
  titulo: string;
  tipo: "pelicula" | "serie";
  sinopsis: string | null;
  anio: number | null;
  generos: string[];
  imagen_portada: string | null;
  imagen_fondo: string | null;
};

export type CatalogResponse = {
  elementos: MediaItem[];
  total: number;
  limit: number;
  offset: number;
};

export function apiPath(path: string): string {
  return `/api/viewtv${path.startsWith("/") ? path : `/${path}`}`;
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiPath(path), {
    ...init,
    credentials: "same-origin",
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Error HTTP ${response.status}`;
    try {
      const data = (await response.json()) as { detail?: string };
      if (data.detail) message = data.detail;
    } catch {
      // La respuesta no siempre contiene JSON.
    }
    const error = new Error(message);
    Object.assign(error, { status: response.status });
    throw error;
  }

  return (await response.json()) as T;
}
