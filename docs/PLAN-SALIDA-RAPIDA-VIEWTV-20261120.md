# VIEWTV — plan de salida rápida: primero producto, después mejoras

Fecha: 20-11-2026.
Regla del usuario: sacar la aplicación lo antes posible **con sus funciones
principales operativas**, y abordar después correcciones no críticas,
refinamientos y optimizaciones.

## Qué cuenta como "VIEWTV funciona"

Se considera **primera versión utilizable** cuando el usuario puede,
desde la interfaz, iniciar sesión con su propio perfil, consultar
su catálogo, generar una solicitud, elegir un resultado, comprobar
el estado de descarga y acceder a un medio disponible en Jellyfin.
Ninguna acción debe corromper la SQLite, duplicar descargas ni mover
archivos ajenos.

**La primera versión con organizador automático** exige además
que un contenido de prueba autorizado y completado se publique
una sola vez en el destino correcto y se detecte en Jellyfin,
con un mecanismo de reversión ensayado.

No declarar estas metas cumplidas basándose solo en salud de
contenedores, pruebas de endpoints públicos o un prototipo sintético.

## Hoja de ruta por bloqueos, sin ampliar requisitos

### Hito A — Estabilizar la aplicación base 0012 (HECHO PARCIALMENTE)

- [x] Diagnosticar API reiniciándose por imagen con migraciones 0008
  sobre SQLite 0012.
- [x] Respaldar SQLite de forma consistente, comprobar su integridad,
  revisión 0012 y SHA-256.
- [x] Recrear exclusivamente la API con la imagen 0012 ya definida
  en Compose; comprobar health y esquema Alembic.
- [x] Verificar interfaz, proxy API, perfiles y seguridad 401, Jellyfin.
- [ ] Confirmación manual de login/logout en el navegador del usuario,
  **sin compartir su PIN**.
- [ ] Prueba visual real del catálogo y una reproducción existente
  con autorización normal del usuario.
- [ ] Revisar el único elemento de cola `fallida` observado en el
  worker; no borrarlo ni reintentarlo a ciegas.

### Hito B — Solicitudes y descarga de prueba (PENDIENTE)

- [ ] Verificar búsqueda y selección en interfaz con un trabajo
  de prueba que el usuario autorice.
- [ ] Comprobar integración real con los proveedores y qBittorrent,
  sin leer ni alterar torrents ajenos.
- [ ] Demostrar seguimiento del trabajo elegido y estados de fallo.
- [ ] El inicio de descargas permanece en
  `VIEWTV_ENABLE_DOWNLOAD_START=false`. Activarlo **solo**
  tras verificación del flujo y autorización para el ensayo real.
- [ ] Establecer procedimiento reversible; no habilitar
  ejecuciones masivas ni cambios de biblioteca por defecto.

### Hito C — Organizador mínimo seguro 0013 (PENDIENTE)

- [ ] Reutilizar la validación de lease, torrent y permisos
  ya probada en sandbox; no añadir nuevas mejoras ajenas a salida.
- [ ] Integrar una autoridad durable única y separada del worker,
  sin rutas de publicación que eludan la autorización.
- [ ] Probar un único medio sintético de extremo a extremo,
  con un solo destino y recuperación manual si hay ambigüedad.
- [ ] Demostrar movimiento seguro y detección en Jellyfin
  con datos autorizados antes de habilitar automatización productiva.

### Hito D — Publicación controlada y cierre (PENDIENTE)

- [ ] Respaldos consistentes de SQLite y configuración, comprobados.
- [ ] Pruebas de autenticación, catálogo, búsqueda, selección,
  descarga, seguimiento, publicación y reproducción.
- [ ] Simular reversión con copias, sin sobrescribir datos vivos.
- [ ] Autorización explícita para activar funcionalidades
  que inicien torrents, muevan medios o cambien producción.
- [ ] Despliegue gradual y monitorización de la API/worker.
- [ ] Cerrar PR en el momento autorizado, no antes.

## Dejar para DESPUÉS de una primera versión funcional

- Mejoras cosméticas y de rendimiento no bloqueantes.
- Nuevas funciones opcionales y automatizaciones complementarias.
- Casuística adicional de errores que no afecte integridad,
  privacidad o seguridad de las operaciones esenciales.
- Pulido o ampliación indefinida de prototipos sandbox ya validados.

## Estado verificado al elaborar el plan

- API **reparada**, imagen `viewtv:predeploy-0012-release`,
  saludable y Alembic en revisión 0012.
- UI Next.js en `127.0.0.1:3000` (HTTP 200),
  proxy a API (HTTP 200), ruta de perfiles (HTTP 200).
- Jellyfin saludable en `127.0.0.1:8097` (HTTP 200).
- Worker activo y descarga automática desactivada.
- Script de humo de solo lectura: **10/10 correcto**.
- PR #2 sigue en borrador; no significa que 0013 esté desplegado.
- **NO verificados aún:** login con PIN, proveedor de búsqueda
  real, una descarga real, organización automática y reproducción
  completa. Nada de esto debe declararse terminado todavía.

## Regla de estimación

No repetir una estimación de varias semanas sin pruebas.
Con la API arreglada, el próximo bloqueador real se determina
por la primera prueba funcional del usuario y del circuito de
descarga. Registrar qué falla y cuánto trabajo concreto exige
antes de comprometer horas o una fecha final.
