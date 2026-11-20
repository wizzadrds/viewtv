# VIEWTV — Publicación de carpetas en Windows: prueba aislada

Fecha: 19 de noviembre de 2026. **Código de desarrollo, NO DESPLEGADO.**

## Problema y resultado

En esta instalación Windows 11 + WSL Ubuntu + Docker, el volumen C:
está montado como DrvFS/9p. El prototipo Linux no puede publicar
carpetas mediante `renameat2(RENAME_NOREPLACE)` sobre ese montaje:
retorna `EINVAL (22)`. No se sustituye por `os.rename()`, que
podría sobrescribir otros archivos.

**Alternativa probada:** la API nativa de Windows
`[System.IO.Directory]::Move()` publica una carpeta completa ya
preparada, con su vídeo y subtítulos, a un nombre de destino que
no existe. Sobre una carpeta temporal en el mismo disco NTFS
se verificaron los rechazos al intentar sobrescribir destinos
ocupados, carpetas vacías ya existentes y colisiones sin distinguir
mayúsculas. La publicación nativa de Windows evita depender de
`renameat2` bajo DrvFS.

Esta evidencia **no equivale a una garantía de recuperación ante
cortes de alimentación o errores reales de hardware**, ni autoriza
por sí sola su uso en la biblioteca multimedia.

## Componentes de solo pruebas

- `scripts/organization_windows_publish_probe.ps1`: prueba exploratoria
  de `Directory.Move` con dos archivos (vídeo y subtítulo),
  carpetas ocupadas, colisiones e interrupción anterior a publicar.
- `scripts/viewtv_windows_publish_sandbox.ps1`: publicador
  deliberadamente restringido a un directorio NUEVO y marcado bajo
  `C:\Users\Public\viewtv-win-sandbox-<GUID>`. Requiere
  `.viewtv-win-sandbox-only` con contenido fijo, staging con forma
  `.viewtv-stage-<id>`, una sola película ficticia con hasta
  19 subtítulos reconocidos y archivos de tamaño <=32 MiB.
  Rechaza archivos no reconocidos, subdirectorios, enlaces de
  reanálisis, nombres reservados de Windows y destinos existentes.
  **No puede publicar en `C:\VIEWTV\media`.**
- `scripts/test_viewtv_windows_publish_sandbox.ps1`: nueve escenarios
  ejecutados en sandbox Windows: película + dos subtítulos, dos tipos
  de colisión, archivo no permitido, subtítulo ajeno, vídeos múltiples,
  rutas manipuladas, falta de marcador e interrupción previa.
- `worker/organization_cross_runtime_probe.py`: prepara el staging
  **solo cuando lo solicita el test Windows**. Valida el marcador,
  carpeta exacta de pruebas y archivos ficticios. Lanza la imagen
  de desarrollo `viewtv:predeploy-0013-dev` con
  `--network none`, `--read-only`, `--cap-drop=ALL` y un único
  directorio de pruebas escribible; comprueba SHA-256 del staging
  contra sus fuentes.
- `scripts/test_cross_runtime_windows_publish.ps1`: Windows crea la
  carpeta aleatoria, genera el vídeo ficticio (~3 MiB) y el subtítulo,
  **invoca WSL para preparar el staging con Docker**, llama al
  publicador nativo de Windows, vuelve a verificar SHA-256 de ambos
  archivos, rechaza el segundo intento y comprueba el origen intacto.
  Al terminar elimina únicamente ese sandbox recién creado.

**Resultados observados:** nueve escenarios de publicador Windows
correctos; cuatro comprobaciones de integración Docker → Windows
correctas (staging verificado, publicación multifichero,
no sobrescritura y origen inalterado). No quedaron directorios
`viewtv-win-sandbox-*` bajo la carpeta temporal utilizada.

## Invocación de prueba (solo entorno de desarrollo)

Desde PowerShell en el equipo local:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv\scripts\test_viewtv_windows_publish_sandbox.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv\scripts\test_cross_runtime_windows_publish.ps1"
```

El coordinador **se ejecuta en PowerShell de Windows**, no intenta
lanzar PowerShell desde WSL: esa dirección devolvía código 1 sin
salida, aun cuando las pruebas de Windows funcionaban. No se ignora
el error ni se interpreta como publicación confirmada.

## Barreras que faltan antes de producción

1. **El publicador actual es solo de sandbox.** No trasladar este
   código sin rediseñar el confinamiento del ejecutor Windows,
   autenticación de mensajes entre Docker/Windows y rutas permitidas.
2. Evitar carreras TOCTOU entre verificación y publicación,
   con identidad del staging ligada al hash y al plan de
   organización, comprobación final de contenido y permisos.
3. Determinar estrategia transaccional ante caída de Windows justo
   en el movimiento; ante resultado ambiguo no repetir publicación:
   conciliar staging, destino y estado de la base antes de reintentar.
4. Exigir en todo momento lease vigente, verificación qBittorrent
   por hash/etiqueta/carpeta, espacio disponible y acceso de
   escritura restringido a destinos autorizados.
5. Validar tamaños de películas reales, restricciones ACL,
   rendimiento, bloqueo de archivos por Jellyfin/antivirus,
   episodios en series existentes y todas las combinaciones de
   subtítulos; el límite de 32 MiB de esta prueba es deliberado.
6. Copias de seguridad nuevas, migración controlada `0012 → 0013`,
   plan de rollback y pruebas de Jellyfin/TV con contenido autorizado.
7. La función no se importa desde el worker de producción ni modifica
   Docker Compose; el inicio automático de torrents sigue desactivado.

**Producción permanece en VIEWTV 0012. Ningún torrent, película o
serie real se ha alterado.**

Documentos relacionados:
[Compatibilidad DrvFS](ORGANIZADOR-COMPATIBILIDAD-WINDOWS.md),
[Cola 0013](ORGANIZADOR-COLA-0013.md),
[Orquestación en sandbox](ORGANIZADOR-ORQUESTACION-SANDBOX.md).

## Refuerzo posterior: autorización y recuperación

Se ha incorporado un plan de autorización temporal firmado con
**HMAC-SHA256**, asociado al sandbox, staging, destino, vencimiento y
SHA-256 de cada archivo, con la clave temporal fuera del montaje de Docker.
El publicador Windows exige ese plan, comprueba la integridad antes y
después de publicar y rechaza datos alterados o autorizaciones caducadas.

Existe además un reconciliador **estrictamente de solo lectura** para
resultados ambiguos: constata si falta el staging, existe el destino o
ambos, valida hashes de la carpeta publicada y nunca reintenta ni borra.
Un destino antiguo puede cotejarse con una firma ya caducada, pero no
puede ser publicado de nuevo con ella.

**20 pruebas del publicador/reconciliador y seis comprobaciones
Docker → Windows superadas.** Es un mecanismo de pruebas; todavía NO
hay un broker de producción con ACL e identidad separadas.
Ver [ORGANIZADOR-AUTORIZACION-RECUPERACION-SANDBOX.md](ORGANIZADOR-AUTORIZACION-RECUPERACION-SANDBOX.md).

## Avance del 20 de noviembre de 2026: identidad NTFS del staging

El plan HMAC de pruebas ahora incluye identificadores NTFS (volumen, carpeta
y archivos); el publicador revalida la identidad antes y después de los
hashes, y rechaza archivos con hardlinks múltiples o reparse points.
Una sustitución por **otro archivo de bytes/SHA-256 idénticos** ya no
coincide con la autorización firmada. Los registros anteriores que no
incluían esta información fallan de forma conservadora.

**No se ha cerrado TOCTOU:** se comprobó que mantener descriptores
abiertos mientras se mueve una carpeta impide `Directory.Move`
en el NTFS de este equipo. Continúan siendo obligatorias identidades
Windows separadas, ACL y revalidaciones del lease en el broker real.
Resultados, pruebas y límites:
[Identidad NTFS y TOCTOU en sandbox](ORGANIZADOR-IDENTIDAD-NTFS-TOCTOU-SANDBOX.md).
