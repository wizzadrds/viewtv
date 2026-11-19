# VIEWTV — Diagnóstico de NTFS/DrvFS y episodios en temporadas existentes

**Fecha:** 19 de noviembre de 2026. **SOLO DESARROLLO; NO DESPLEGADO.**

La instalación real continúa con API/worker `0012`, web real en
`http://127.0.0.1:3000` y bibliotecas montadas en solo lectura.
No se ha iniciado ningún torrent ni se ha modificado `C:\VIEWTV\media`.

## 1. Diagnóstico del entorno Windows

WSL Ubuntu monta `/mnt/c` mediante **9p (DrvFS)**. Por tanto, un resultado
positivo de filesystem ext4 en `/tmp` NO garantiza lo mismo en Windows.

Se ha ejecutado `worker/organization_drvfs_probe.py` de manera controlada
sobre una **carpeta temporal única en `C:\Users\Public`**, con marcador
de prueba, y limpieza de los archivos ficticios al salir. Ningún archivo
real de la biblioteca, torrent, DB o credencial se montó ni abrió.

| Operación en DrvFS/NTFS | Resultado de prueba |
|---|---|
| Publicar una carpeta nueva con `renameat2(RENAME_NOREPLACE)` | **No soportado: EINVAL (22)** |
| Evitar sobrescribir una carpeta existente | Protegida en la prueba |
| `O_NOFOLLOW` sobre enlace simbólico | Protegido: ELOOP (40) |
| `fsync` de directorio | Admitido en la prueba |
| Detectar nombres equivalentes por mayúsculas/minúsculas | Sí, Windows es insensible en este directorio |
| Publicar un **archivo** mediante `os.link` | Admitido |
| Rechazar `os.link` si el archivo ya existe | Protegido |
| Copiar y verificar archivo ficticio de 9 MiB en varios bloques, con SHA-256 | Correcto |

**También se repitió el ensayo dentro de un Docker desechable** mediante
`worker/organization_windows_docker_probe.py`: red desactivada,
sistema base en solo lectura, capacidades retiradas, único volumen
escribible el directorio ficticio del test, proyecto montado solo lectura.
Se comprobó una copia ficticia de unos 4 MiB, enlace duro sin sobreescribir
y el mismo **EINVAL (22)** de `renameat2`.

**Conclusión:** la publicación atómica de directorios actual del sandbox
NO puede trasladarse sin modificaciones a NTFS. La publicación de un
archivo individual mediante enlace duro se ha probado, pero esto no
certifica aún todos los permisos/ACL ni el funcionamiento con bibliotecas
reales. No usar `os.rename` como reemplazo sin garantía de
no sobrescritura.

## 2. Prueba de añadir un episodio a una temporada existente

Se ha añadido el prototipo `worker/organization_existing_season_sandbox.py`
con `publish_test_existing_episode`, limitado a **`/tmp` con marcador**.

- Requiere una serie y temporada **ya existentes**, con la estructura
  `Series/Nombre/Temporada NN/Nombre - SnnEnn.mkv`.
- Rechaza cualquier grupo de varios archivos, subtítulos incluidos.
  Es una medida deliberada: publicar varios ficheros uno a uno podría
  dejar la temporada incompleta tras una caída.
- Abre directorios mediante descriptores con `O_DIRECTORY|O_NOFOLLOW`.
  Rechaza carpetas y nombres ambiguos, enlaces simbólicos y archivos
  duplicados, incluso por diferencias de mayúsculas.
- Crea un staging privado con ID de descarga dentro de la temporada,
  copia el vídeo y verifica tamaño/origen/destino mediante el copiador
  ya probado. Nunca borra el archivo de descarga.
- Publica el archivo mediante `os.link(src_dir_fd=..., dst_dir_fd=...,
  follow_symlinks=False)`: la creación del nombre falla si el destino
  ya existe. Rechaza las colisiones simultáneas.
- Solo tras publicar y sincronizar elimina **el duplicado temporal
  creado por esta misma prueba** y la carpeta vacía de staging.
  Si falla o se corta, conserva el staging para revisión.
- El coordinador `worker/organization_runner_sandbox.py` detecta una
  temporada existente y usa este mecanismo de forma estricta. Un
  fallo posterior a la publicación **no permite copiar de nuevo**:
  el destino detectado se marca `requiere_revision`.

## 3. Validaciones

- `backend/tests/test_organization_existing_season_sandbox.py`:
  **13 pruebas** sobre carpetas ficticias: episodios previos intactos,
  duplicados, colisión de mayúsculas, symlinks, interrupciones, staging,
  carrera de publicación y prohibición de publicar varios archivos.
- `backend/tests/test_organization_runner_sandbox.py`:
  **4 pruebas nuevas** de integración con cola: publicación, reinicio
  después de publicar, subtítulos bloqueados, episodio ya existente.
- Diagnósticos Windows realizados tanto en WSL como en un contenedor
  desechable con montajes estrictamente limitados.
- Suite completa backend: **488 pruebas aprobadas**, con 2 advertencias
  de deprecación conocidas. Ruff limpio y `git diff --check` correcto.

## 4. Límites antes de habilitarlo sobre bibliotecas reales

1. La protección de `/tmp` y el límite actual de 32 MiB por archivo
   siguen vigentes: NO es todavía una función de organización real.
2. Falta decidir estrategia para carpetas nuevas en DrvFS, ya que
   `renameat2(RENAME_NOREPLACE)` no está disponible.
3. Falta una estrategia transaccional para publicar vídeo + subtítulos,
   varios episodios o temporadas sin exponer contenido incompleto.
4. Antes de cualquier escritura en NTFS de producción: permisos/ACL
   mínimos, espacio libre, tamaños reales, heartbeat también durante
   llamadas bloqueantes, revalidación qBittorrent y DB antes de publicar,
   idempotencia tras cortes y rutas confinadas.
5. Migración `0012→0013` únicamente tras backup nuevo y simulación
   de restauración; mantener inicio automático desactivado.
6. Prueba real autorizada y escaneo/reproducción Jellyfin, acceso TV
   y reconciliación del PR en GitHub.

**No fusionar ni desplegar como función operativa todavía.**

Ver también [cola 0013](ORGANIZADOR-COLA-0013.md),
[orquestación aislada](ORGANIZADOR-ORQUESTACION-SANDBOX.md) y
[copiador de sandbox](ORGANIZADOR-COPIA-SANDBOX.md).
