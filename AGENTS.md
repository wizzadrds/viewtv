# VIEWTV — Instrucciones operativas para futuras sesiones

Estas instrucciones son persistentes en el repositorio y tienen prioridad operativa para trabajar en VIEWTV.
No sustituyen las autorizaciones explícitas del usuario ni las restricciones del conector.

## Entorno obligatorio: Ubuntu dentro de WSL

- Desarrollar, editar, ejecutar pruebas backend, administrar Git, hacer commits/push y consultar Docker **en Ubuntu 24.04 (WSL)** del equipo `LAPTOP-V2QSMC01`, usuario Ubuntu `viewtv`, usando el conector **Remote Desktop Commander**.
- **Único árbol de desarrollo permitido:**
  `/home/viewtv/projects/viewtv-broker-0013-20261119`
- **Única rama autorizada:** `viewtv-seguimiento-descargas-0012`. Nunca trabajar sobre `main`.
- La shell inicial de WSL invocada por el conector puede estar en `/mnt/c/Users/.../node_modules/...`, **NO dentro del proyecto**. Entrar expresamente en el directorio correcto antes de cualquier operación.
- Ejemplo de acceso desde Windows mediante el conector:
  `wsl.exe --distribution Ubuntu-24.04 --user viewtv --exec /bin/bash -lc 'cd /home/viewtv/projects/viewtv-broker-0013-20261119 && git status --short --branch'`
- Antes de editar, comprobar `whoami`, `pwd`, `git branch --show-current` y `git status`. Nunca asumir que WSL empezó en el directorio correcto.
- **No desarrollar en PowerShell Windows ni en la copia `/home/viewtv/projects/viewtv`**, que está en otra rama (`inventario-trabajo-local`) y contiene archivos `.bak` y no versionados del usuario.
- PowerShell de Windows se usa **únicamente** para las pruebas NTFS/ACL, broker/cuentas/servicios cuando sean necesarias, y la interfaz remota hacia Ubuntu. Proteger `C:\VIEWTV\media` real; 0013 solo en `C:\Users\Public\viewtv-win-sandbox-<GUID>` con marcador explícito, nunca fuera de sandbox sin autorización nueva.

## Permisos comprobados el 20-11-2026

- La sesión PowerShell elevada que el usuario abrió devolvió `True` para el rol Administrador.
- La propia sesión PowerShell del conector devolvió `CONNECTOR_ADMINISTRATOR=True`, verificado de forma independiente. **No pedir más elevación por defecto.**
- Aunque el conector esté elevado, algunas órdenes (`net`, `sc`, `runas`, etc.) están restringidas por su configuración. No eludir restricciones, no asumir que existen cuentas Windows independientes y no dar por cerrado TOCTOU sin pruebas desde SIDs realmente separados.
- La disponibilidad del conector y sus permisos pueden cambiar; comprobarlos de nuevo al intervenir.

## Disciplina de cambios

- Antes de modificar archivos o bases existentes, crear un `tar.gz` con **solo los archivos implicados** en `~/viewtv-backups/<hito>-<AAAAMMDD-HHMMSS>.tar.gz`; verificar `tar -tzf` y `sha256sum`, e incluir ruta + hash en la documentación del hito. Si un archivo es nuevo, documentar que no existe anterior que respaldar.
- No modificar la SQLite de producción sin respaldo nuevo verificado. API y worker deben compartir versión y esquema. `VIEWTV_ENABLE_DOWNLOAD_START=false`; organización desactivada por defecto.
- Prohibido `git add .`, `git clean`, `git reset --hard`, `git push --force`, borrar `.bak`, `docker compose down -v` o tocar torrents ajenos.
- Cada entrega importante requiere **código + tests + documentación + commit en español + push** en la rama autorizada. El PR #2 permanece en borrador y **no se fusiona** sin permiso.
- Respetar la secuencia de fases solicitada por el usuario. Al final de cada fase, informar de lo realizado, supuestos y pendientes, y **detenerse**.
- Incidencia pendiente observada: `viewtv-api-1` reiniciaba con imagen `viewtv:local` mientras el worker ejecutaba `viewtv:predeploy-0012-release`, con error `Can't locate revision identified by '0012_inicio_torrent'`. No atribuir causa definitiva ni cambiar producción sin comprobaciones y respaldos.
- Ver `docs/ENTORNO-CONECTOR.md` y `docs/ORGANIZADOR-ENTREGA-PRIVADA-NTFS-SANDBOX.md` para evidencia, limitaciones y resultados reales.

## Confidencialidad

No leer, imprimir ni compartir contenido de `.env`, PIN, claves de firma o secretos. No confundir tener permisos de administrador con permiso del usuario para actuar sobre producción.
