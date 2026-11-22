# VIEWTV — Jackett, acceso desde la televisión y actualizaciones compartidas

**Fecha:** 22/11/2026, Europe/Madrid
**Equipo:** LAPTOP-V2QSMC01, Windows 11 + WSL Ubuntu 24.04, Docker Desktop
**Worktree:** `/home/viewtv/projects/viewtv-broker-0013-20261119`
**Rama:** `viewtv-seguimiento-descargas-0012`, PR #2 OPEN/DRAFT

## Resumen real de esta intervención

Se ha comprobado Jackett desde la API y desde el worker sin
realizar búsquedas de títulos, sin solicitar torrents ni descargar
archivos. Se ha desplegado un sistema de aviso y actualización
automática **de la interfaz Web** que funcionará en cualquier
navegador compatible que abra el mismo servidor, también
en una televisión.

**No se ha realizado todavía una prueba desde una televisión
real.** El ordenador responde en `127.0.0.1:3000` pero
**NO** en su IP Wi-Fi `192.168.1.138:3000`. Falta habilitar
ese acceso en Windows, operación administrativa que el
conector remoto bloquea y por ello **no se ha ejecutado**.
Los pasos para el propietario están más abajo.

## Jackett: tres indexadores configurados

Lectura autenticada de capacidades Torznab desde el
endpoint agregado `t=indexers` y de cada `t=caps`:

| Indexador | Configurado | `movie-search` | `tv-search` | Familias de categorías |
| --- | --- | --- | --- | --- |
| `divxtotal` | Sí | Sí | Sí | 2000, 4000, 5000, 8000 |
| `dontorrent` | Sí | Sí | Sí | 2000, 5000 |
| `mejortorrent` | Sí | Sí | Sí | 2000, 3000, 5000 |

La instancia informa de **655 definiciones**, **3 configuradas**
y **652 no configuradas**. El worker de ViewTV confirma
también **3 indexadores configurados** mediante lectura real.
Que respondan `t=caps` **NO prueba** que sus sitios externos
respondan a búsquedas reales, ofrezcan fuentes autorizadas,
o que contengan películas/episodios específicos.

Nunca se imprimen API keys, PIN, passkeys, torrents, URLs
de descarga, hashes o títulos de resultados. La información
de índices se leyó sin usar `t=search`, `t=movie` o
`t=tvsearch`; **no se inició descarga alguna**.

Los scripts seguros de lectura se guardan en
`scripts/viewtv_jackett_indexers_probe_0013.py` y
`scripts/viewtv_jackett_caps_probe_0013.py`.
El primero solo informa el listado de nombres
y conteos; el segundo analiza las categorías y modos.

Fuente oficial Jackett:
https://github.com/Jackett/Jackett#api

## Actualización de la web en PC y televisión

**Una instalación**, un único servidor
`viewtv-frontend-1`, misma URL por red local.
La tele **no almacena una copia propia de los
archivos de ViewTV**: los obtiene del servidor.

Implementación instalada:

- `frontend/scripts/generate-release.cjs` genera un
  identificador estable SHA-256 reducido, basado en
  los archivos del frontend (sin credenciales).
  El Dockerfile lo ejecuta **antes** de cada
  `next build`. Cuando cambia el código de
  interfaz cambia el identificador.
- `frontend/app/api/app-version/route.ts` publica
  el identificador mediante
  **`GET /api/app-version`**, sin sesión necesaria,
  con `Cache-Control: private, no-store` para
  evitar respuestas viejas en la televisión.
- `frontend/components/app-update-monitor.tsx`
  consulta esa ruta cada **60 segundos** mientras
  la pestaña esté visible; también al volver
  a primer plano o recuperar conexión.
- Cuando ve una nueva versión, presenta un aviso
  con el botón **«Actualizar ahora»**, navegable
  mediante el mando a distancia.
- Si no hay actividad durante **90 segundos**,
  y no hay vídeo, ficha/modal ni campo de
  entrada activo, recarga automáticamente.
  **Nunca interrumpe deliberadamente una película
  o ficha abierta.**
- `frontend/app/layout.tsx` monta el monitor
  en todas las vistas, incluida la pantalla
  de elección de perfil y el catálogo.
  `frontend/app/globals.css` proporciona
  estilo adaptable a televisor/móvil.
- No hay Service Worker; la PWA actualmente
  utiliza un manifiesto. El funcionamiento
  por navegador no requiere instalar
  APK, app Samsung Tizen o LG webOS.

**Condiciones importantes**:
1. La televisión debe cargar esta versión
   **una primera vez**; una pestaña anterior
   sin monitor no recibirá la actualización
   hasta abrir de nuevo o actualizar la página.
2. Las actualizaciones de API y catálogo
   de metadatos se reflejan desde el mismo
   servidor, sin copiarlas a la tele.
   Las modificaciones de interfaz requieren
   construir y **desplegar** el frontend, no
   basta hacer `git push`.
3. El hash se genera automáticamente **cuando
   se utiliza el Dockerfile oficial**.
   Las compilaciones manuales fuera de Docker
   deben ejecutar primero
   `node scripts/generate-release.cjs`.
4. Los navegadores de algunos televisores
   pueden suspender JavaScript; al volver
   a la app se comprueba de nuevo.
5. La sesión de la televisión es independiente
   de la de `localhost` en el PC y necesitará
   iniciar sesión con el perfil y PIN.
6. La conexión HTTP local no cifra el PIN,
   por lo que **solo se recomienda una red
   doméstica Wi-Fi privada y de confianza**,
   sin abrir puertos en el router.
   Para dispositivos externos a esa LAN,
   se necesitará primero HTTPS autenticado.

## Observaciones de Windows / conectividad

- IP del adaptador **Wi-Fi**: `192.168.1.138/24`.
- Categoría de red Wi-Fi: **Private**.
- CloudflareWARP: perfil **Public**, no debe
  exponerse por ese adaptador.
- IP interna virtual WSL: `192.168.32.1`,
  no es la URL para la televisión.
- Windows escucha TCP 3000 solo en
  **`127.0.0.1:3000`**.
- `http://127.0.0.1:3000/` devuelve HTTP 200.
- `http://192.168.1.138:3000/` desde el
  mismo ordenador es **NO DISPONIBLE**.
- Servicio Windows `iphlpsvc`: **Running**.
- Sesión del conector: **Administrador**,
  pero el comando `netsh` es **bloqueado**
  por las restricciones del conector.
  **No se intentó eludir esa restricción.**
- No se observaron reglas de firewall
  explícitas de puerto 3000 en la
  comprobación de solo lectura.

### Pasos manuales del propietario (PowerShell Administrador)

**Ejecutar solo si la tele está en tu misma
red doméstica Wi-Fi, no en red de invitados.**
Primero confirmar que la IP del PC sigue siendo
`192.168.1.138`:

```powershell
Get-NetIPAddress -InterfaceAlias "Wi-Fi" -AddressFamily IPv4
netsh interface portproxy show v4tov4
```

Si **ya existe** una regla para
`192.168.1.138:3000`, detenerse y revisarla:
**no sobrescribir reglas existentes**.

Si la IP sigue siendo la indicada y NO existe
ese reenvío, ejecutar:

```powershell
netsh interface portproxy add v4tov4 listenaddress=192.168.1.138 listenport=3000 connectaddress=127.0.0.1 connectport=3000 protocol=tcp
New-NetFirewallRule -Name "VIEWTV-TV-LAN-3000-0013" -DisplayName "ViewTV - TV en Wi-Fi privada" -Direction Inbound -Action Allow -Profile Private -Protocol TCP -LocalPort 3000 -LocalAddress 192.168.1.138 -RemoteAddress 192.168.1.0/24
Invoke-WebRequest -UseBasicParsing -Uri http://192.168.1.138:3000 -TimeoutSec 10
```

No abrir el puerto 3000 en el router y **nunca**
usar `0.0.0.0` como dirección de escucha para
este procedimiento. La regla permite únicamente
clientes en `192.168.1.0/24` hacia la IP Wi-Fi
del ordenador, perfil de red privada.

Si se cambia de IP, **no reutilizar**
este comando sin verificar la configuración.

Para **deshacer exclusivamente** la configuración
creada por estos pasos:

```powershell
netsh interface portproxy delete v4tov4 listenaddress=192.168.1.138 listenport=3000 protocol=tcp
Remove-NetFirewallRule -Name "VIEWTV-TV-LAN-3000-0013"
```

Referencias oficiales Microsoft:
https://learn.microsoft.com/en-us/windows-server/networking/technologies/netsh/netsh-interface-portproxy
https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule

## Prueba manual de televisión (aún pendiente)

Después de que PowerShell devuelva 200 desde
la IP Wi-Fi, hacer esta prueba **sin descargas**:

1. Conectar televisión y ordenador al mismo
   Wi-Fi privado (no invitados, sin aislamiento
   entre dispositivos).
2. Abrir el navegador del televisor e introducir
   **`http://192.168.1.138:3000`**.
   **No usar `localhost` en la televisión.**
3. Iniciar sesión con el perfil de ViewTV.
4. Abrir «Explorar», comprobar carátulas y
   desplazamiento con la cruceta del mando.
5. Abrir una serie, cambiar de temporada,
   leer episodios, volver atrás. **No pulsar
   «Solicitar episodio»** durante esta prueba.
6. Abrir biblioteca local y probar reproducción
   de una película autorizada: imagen, sonido,
   pausa y salida; observar errores si el
   navegador del televisor no soporta el códec.
7. Probar **actualización futura** cuando se
   despliegue una **nueva versión** de frontend:
   verificar aviso y recarga en inactividad.
   Esta última prueba exige una segunda versión
   diferente; **no se ha probado aún
   físicamente en TV**.

En televisores cuyo navegador es antiguo,
Android TV/Google TV puede tener navegadores
compatibles; Samsung Tizen/LG webOS depende
de su versión concreta. No se afirma que
ViewTV sea hoy una aplicación nativa instalable.

## Validación de despliegue realizada

- Backup previo de **solo archivos implicados**:
  `/home/viewtv/viewtv-backups/television-actualizaciones-pre-20261122-211000.tar.gz`,
  SHA-256 `83923988b3df14c93477ab8293404c87f3e31aa0850a26afb7a0096dc6116da0`,
  `tar -tzf` comprobado. Los nuevos archivos
  no tenían contenido anterior que respaldar.
- TypeScript `tsc --noEmit --incremental false` **PASS**;
  ESLint archivos afectados **PASS**.
- `docker build` del frontend **PASS**,
  ruta Next dinámica `/api/app-version`.
  Identificador de la versión desplegada:
  `v1-8f625bb0ec5d02800240`.
- Imagen frontend nueva:
  `viewtv-frontend:tv-auto-update-0013`;
  `viewtv-frontend-1` **healthy**.
  Solo se recreó el contenedor frontend.
- Compose nuevo y anterior **PASS**,
  sin mostrar secretos. API, catalogador,
  worker y Jellyfin no fueron recreados.
- `GET http://127.0.0.1:3000/api/app-version`
  **HTTP 200**, revision correcta,
  `Cache-Control` incluye `no-store`.
- Portada HTML **HTTP 200**.
- Smoke de producción de solo lectura:
  **10/10 PASS**. API, Jellyfin y
  frontend siguen healthy.
- Publicador Windows `VIEWTV - Publicador
  automatico 0013`: **Ready**, nivel
  **Limited**, resultado último **0**.
- Jackett worker y API identifican 3
  indexadores. Ninguna llamada `t=search`
  ni descarga fue emitida.
- No se modificaron bases SQLite,
  esquema Alembic, torrents ni
  `C:\VIEWTV\media`.

### Reversión del nuevo frontend

La nueva capa es aislada. Desde la rama
autorizada, ejecutar:

```bash
bash scripts/viewtv_tv_deploy_0013.sh rollback
```

Vuelve **solo** al frontend
`viewtv-frontend:series-episodios-0013`,
sin modificar API, SQLite ni Jellyfin.
No usar `docker compose down -v`.

Si la prueba de LAN falla, primero revisar
`Get-NetIPAddress`, reenvío y firewall
sin abrir la red pública. El acceso
por navegador de TV sigue pendiente hasta
una comprobación desde el dispositivo real.

## Próximas mejoras posibles

- Confirmar modelo y sistema del televisor,
  compatibilidad con mando a distancia y HLS.
- Reservar la IP Wi-Fi en el router, para
  conservar la URL tras reiniciar el PC.
- Valorar HTTPS privado antes de dar
  acceso más allá de la red local.
- Mantener la publicación segura de episodios
  de series como tarea separada de sandbox,
  no abrir permisos NTFS en este hito.
