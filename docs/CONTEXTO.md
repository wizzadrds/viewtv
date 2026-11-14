# CONTEXTO DEL PROYECTO — VIEWTV

Documento de traspaso. Léelo entero antes de tocar nada. Si algo aquí contradice a tu intuición, manda el documento.

## 1. Qué es esto

Aplicación doméstica autohospedada con interfaz tipo Netflix para ver cine en un televisor con el mando a distancia. El catálogo es permanente y barato; el vídeo es efímero: se descarga al pedirlo, se reproduce mientras descarga, y se borra solo al terminar. Un chat permite pedir títulos por texto con prioridad máxima. Lo que no se encuentra queda en una lista de espera que reintenta y sobrevive a apagones.

No es un gestor de biblioteca permanente. No es un clon de Netflix para varios usuarios. No se expone a Internet.

## 2. Glosario

- **Indexer**: buscador de enlaces torrent. La app no los consulta uno a uno, habla con un agregador.
- **Torznab**: protocolo HTTP estándar para consultar indexers. Lo hablan Jackett y Prowlarr.
- **Prowlarr / Jackett**: agregadores de indexers. Devuelven resultados en JSON por Torznab.
- **qBittorrent**: cliente de descargas, con API web.
- **Jellyfin**: servidor multimedia. Sirve y transcodifica el vídeo; la app no reimplementa reproductor.
- **TMDB**: base de datos de cine. Aporta título, sinopsis, carátulas y reparto.
- **Lease**: bloqueo temporal de un trabajo para que dos procesos no lo procesen a la vez.
- **Backoff**: espera creciente entre reintentos.
- **LRU**: se borra primero lo usado hace más tiempo.
- **PWA**: web instalable que se abre a pantalla completa como una app.
- **NVENC**: codificador de vídeo por hardware de NVIDIA.

## 3. Entorno real

- Windows 11 + WSL2 (Ubuntu 24.04) + Docker Desktop con integración WSL.
- Se clona y se ejecuta desde el sistema de archivos de WSL (`~/projects/viewtv`), **nunca** desde `/mnt/c`.
- Portátil con 32 GB de RAM, GPU NVIDIA, SSD pequeño.
- El portátil **no está siempre encendido**: se enciende a mano cuando se va a ver algo. Sin Wake-on-LAN.
- Cliente: Android TV / Fire TV con TV Bro o Silk. La app es una PWA.
- Dos perfiles con PIN, uso doméstico, red local.
- Ya funcionando en la máquina: Docker, Jellyfin, qBittorrent, Prowlarr.

## 4. Decisiones cerradas

No reabrir sin ADR que lo justifique.

1. Fuentes por **adaptador Torznab genérico**, válido para Jackett y para Prowlarr. La app **nunca** parsea HTML.
2. Jellyfin es el motor de reproducción y de biblioteca.
3. Cola **durable en SQLite**, jamás en memoria. Leases de 120 s con heartbeat de 30 s, en transacción.
4. Prioridades fijas: **P0** chat, **P1** ficha o fijado, **P2** descubrimiento automático.
5. Caché en `CACHE_DIR` con cuota configurable (80 GB por defecto), TTL de 48 h tras visionado y expulsión LRU. La base de datos nunca vive dentro de la caché.
6. Descarga secuencial con primeros y últimos trozos primero. Reproducción a partir del 15 % o 400 MB.
7. Colchón de reproducción en `/dev/shm`.
8. Perfil de calidad por defecto 1080p H.264/AAC. 4K solo si el cliente lo reproduce en directo.
9. PWA, no envoltorio nativo.
10. Interfaz, logs, documentación y mensajes de commit en español de España.

## 5. Fuentes e indexers

**Hecho verificado**: el repositorio de definiciones de Prowlarr (carpeta activa `v11`, actualizada el 1 de noviembre de 2026) **no tiene** definición de DivxTotal, DonTorrent, MejorTorrent, EliteTorrent, TorrentLand, DivTeam, XbytesV2, HD-Spain ni ZonaQ. Solo existen `puntotorrent` y `hdolimpo`, ambas privadas. Por eso la búsqueda no puede montarse solo contra Prowlarr.

- Jackett cubre las públicas españolas: DivxTotal, DonTorrent, MejorTorrent, EliteTorrent. Los nombres exactos de sus definiciones están **pendientes de verificar** en la interfaz de Jackett, buscando "spanish" en "Add Indexer".
- Prowlarr aporta las privadas con definición: PuntoTorrent, HD-Olimpo.
- Endpoint del adaptador: `GET {BASE}/api/v2.0/indexers/all/results/torznab/api?apikey=<k>&t=search&q=<q>&cat=2000,5000`.
- Filtrado en cliente tras la respuesta: descartar sin seeders, sin pista castellano, fuera de perfil de calidad o por encima del tamaño máximo.
- Fallos: 429, 503 o timeout → indexer marcado caído 30 min, se registra y se sigue. Un indexer caído nunca tumba una búsqueda.
- Panel con estado por indexer, contador de fallos e interruptor para desactivar uno sin tocar el agregador.
- Aviso en la UI cuando todos estén caídos, distinguiendo "sin fuentes" de "sin buscadores".
- Los foros de descarga directa (Exvagos, Piratawarez, ForoWarezPirata) **no** son buscables por API: fuera del alcance, solo descarga manual.

## 6. Ciclo de vida del vídeo

Estados: `pendiente → buscando → descargando → listo → en_reproduccion → visto → expira → borrado`. Más `fallido`, `vigilando`, `fijado`, `cancelado`.

1. Al pulsar "Ver ahora": buscar por `tmdb_id`, aplicar perfil y filtro castellano, elegir la mejor opción y encolar.
2. Si ya está en caché, reproducir al instante.
3. Al 90 % de visionado, marcar `visto` y programar borrado a las 48 h.
4. Al borrar: archivo, torrent y entrada de Jellyfin. Se conservan metadatos y el estado "disponible bajo pedido".
5. Concurrencia máxima: 1 descarga y 1 reproducción.

Reglas de espacio: cuota configurable; al 90 % se expulsa por LRU entre los vistos no fijados; con menos de 15 GB libres no se aceptan solicitudes y se avisa. Nunca se borra lo que se reproduce ni lo que descarga.

## 7. Cola durable

- Tabla `solicitud` con `prioridad`, `estado`, `intentos`, `proximo_intento`, `locked_until`, `heartbeat`, `motivo_fallo`, `idempotency_key` única por `tmdb_id` + resolución + perfil.
- Reclamación: `estado='pendiente' AND proximo_intento <= now() AND (locked_until IS NULL OR locked_until < now()) ORDER BY prioridad ASC, proximo_intento ASC`, en transacción.
- Al arrancar se reconcilia contra qBittorrent: torrent presente → reanudar sin consumir intento; ausente → devolver a `pendiente`.
- Backoff: 5 min, 15 min, 45 min, 2 h, 6 h, 12 h, 24 h. Al octavo intento, estado `vigilando` con comprobación cada 24 h.
- Un job en `vigilando` que encuentra fuente vuelve a `pendiente` con su prioridad original.
- Pantalla "Lista de espera" con estado, motivo, intentos, próximo intento y botones Reintentar y Quitar.

## 8. Descubrimiento

Bucle permanente mientras el equipo esté encendido, ciclos de 20 min, máximo 40 búsquedas por ciclo. Nunca adelanta a una prioridad superior. Por defecto solo enriquece metadatos y la fila "Novedades"; el relleno de descargas es un ajuste con tope de GB. Modo simulación disponible.

## 9. Chat

Dominio cerrado a cine y catálogo. Intenciones: `buscar_y_encolar`, `consultar_disponibilidad`, `borrar`, `pausar`, `saludo`. Parser determinista por patrones y búsqueda difusa en TMDB; Ollama opcional, nunca obligatorio.

Flujo: extraer título y año → multi-search → tarjeta de confirmación con póster → al confirmar, solicitud P0 y "buscando, te aviso". Si TMDB no resuelve: "no la encuentro, ¿cómo se llama exactamente?" con tres sugerencias. Si resuelve pero no hay fuentes en castellano: decirlo y dejar en vigilancia. Nunca afirma disponibilidad sin haber consultado.

## 10. Arquitectura y límites

- Web (Next.js) no toca SQLite, Jellyfin ni secretos.
- API (FastAPI) valida, autentica y es la única puerta de la interfaz a los datos.
- SQLite en volumen persistente, fuera de la caché.
- Worker independiente con APScheduler. Nunca dentro del proceso web.
- Jellyfin externo, consumido con credenciales solo en el servidor.

## 11. Pantallas

Perfil con PIN grande. Inicio con filas horizontales: Continuar viendo, Novedades, Tendencias, Por género, Fijados. Detalle con backdrop, sinopsis, año, duración, géneros, reparto, calidad, audio, estado de caché, botones Ver ahora, Mantener y Borrar, y similares. Búsqueda con teclado en pantalla. Chat con burbujas. Lista de espera. Reproductor con barra que se oculta, salto de 10 s, subtítulos y posición memorizada. Panel de administración de escritorio con cola, indexers, almacenamiento, ajustes y logs. Estados vacíos, de error, de carga y de servidor apagado. Skeletons, nunca spinners.

**Pendiente de decisión**: orientación de las portadas. La especificación decía pósters 2:3 verticales en las filas y backdrops 16:9 solo en detalle. Se ha estado trabajando en horizontal sin ADR. Ver tarea de ADR.

## 12. Estética

Fondo #0B0B0F, acento #E50914, tipografía Inter, esquinas redondeadas, difuminados, transiciones 200 ms, foco con anillo blanco de 3 px y escala 1.05, sin scrollbars, `prefers-reduced-motion` respetado, referencia 1920x1080 escalable.

## 13. Seguridad

PIN con Argon2, JWT en cookie `httpOnly`, rate limit en login, chat y panel, validación Pydantic y TypeScript estricto, secretos solo en servidor, nada expuesto a Internet.

## 14. Datos

`usuario`, `perfil`, `ajuste`, `pelicula`, `serie`, `temporada`, `episodio`, `genero`, `persona`, `reparto`, `archivo_cache`, `solicitud`, `descarga`, `mensaje_chat`, `log_agente`, `fuente_indexer`, `exclusion`. Alembic desde el primer commit, índices y claves foráneas, `tmdb_id` único.

## 15. Reglas de trabajo

- Fases cerradas y revisadas. No se avanza sin pedido expreso.
- Al final de cada fase: qué se hizo, qué se supuso, qué queda. Y parar.
- Un commit por entregable, en `main`, mensajes en español.
- Nada de retoques visuales durante la fase 1 salvo el ADR de portadas.
- Al crear un archivo, una línea explicando para qué sirve.
- Verificar firmas reales de las API antes de usarlas. Si algo no es viable, alternativa y justificación.
- Nunca commitear `.env` ni secretos.

## 16. Trampas conocidas

- Prowlarr no cubre las fuentes públicas españolas.
- Los indexers cambian de dominio a menudo; el vigente sale de su Telegram, no de Google.
- El navegador de la tele traduce la cruceta a teclas: la navegación se prueba así.
- Con MKV el índice va al final: sin la regla de trozos primero, la reproducción progresiva falla.
- El archivo es `worker/tmdb_enrichment.py`; se ha escrito varias veces con la errata `tmbd`.
- La caché en `/tmp` se borra al reiniciar.

## 17. Estado actual

- **Rama principal remota (`origin/main`)**: contiene el inventario documental y el ADR 0001 aceptado. No contiene todavía la implementación local de la fase 1.
- **Rama de trabajo local**: `inventario-trabajo-local`. Incluye la implementación, las correcciones, las pruebas y los entregables de cierre de fase 1.
- **Último commit local verificado**: `9405d23` (`Documentar fuentes técnicas de arquitectura`).
- **Último commit conocido en `origin/inventario-trabajo-local`**: `005e0ef`. Los commits posteriores siguen únicamente en el repositorio local.
- **Árbol de trabajo**: limpio en la última comprobación.
- **Fase 1**: cerrada tras superar las verificaciones locales de backend, frontend, Docker Compose, salud de API, migraciones y concurrencia de la cola.
- No se ha realizado push, PR ni merge de los últimos cambios a `main`.

## 18. ADR pendientes

No hay ADR pendientes conocidos.

- `0001-orientacion-de-portadas.md`: aceptado.
- Decisión: póster vertical 2:3 en todas las filas del catálogo.
- Estado: decisión documentada; implementación visual sujeta al alcance de su fase correspondiente.
- No se exige backdrop en la ficha de detalle.

## 19. Siguiente tarea

La fase 1 está cerrada. No hay una fase 2 definida todavía en este documento.

El siguiente alcance deberá acordarse expresamente antes de modificar código. No adelantar funcionalidades ni reabrir decisiones cerradas sin un ADR que lo justifique.

Antes de integrar el trabajo local en `main`, se deberá revisar y autorizar expresamente el procedimiento de publicación.

## 20. Criterios de la fase 1 (cerrada)

Criterios originales y resultado de la última verificación local:

- `docker compose up -d` levanta los servicios y `/health` responde: **verificado**.
- `alembic upgrade head` crea el esquema en una base vacía: **verificado previamente en una base temporal aislada**. La base del contenedor está en `0003_metadatos_tmdb (head)`.
- Dos procesos reclamando el mismo trabajo no lo duplican: **verificado mediante prueba multiproceso**.
- `ruff` y `pytest`: **verificados**, con 41 pruebas superadas y Ruff sin errores.
- Frontend: comprobaciones de TypeScript, ESLint y build de producción **superadas**.
- `docker compose config --quiet`: **superado**.

La última ejecución registró dos advertencias de deprecación durante pytest, sin fallos. No se consideran bloqueantes para el cierre.

## 21. Lo que no se hace

Sin reproductor propio. Sin scraper de HTML. Sin cola en memoria. Sin base de datos en la caché. Sin Wake-on-LAN. Sin exponer a Internet. Sin adelantar fases.
