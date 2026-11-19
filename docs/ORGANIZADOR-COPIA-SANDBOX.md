# VIEWTV — Ejecutor de copia, prototipo en sandbox (0013)

Fecha: 19 de noviembre de 2026.

**SOLO DESARROLLO. NO CONECTADO A PRODUCCIÓN NI AL WORKER.**

## Qué funciona

`worker/organization_copy_sandbox.py` implementa `publish_test_plan`
sobre rutas de prueba bajo el directorio temporal de Linux, con marcador
`.viewtv-organization-test-only` y valor
`VIEWTV_ORGANIZATION_TEST_SANDBOX_V1`. Nunca acepta `/media`.

El origen es `<sandbox>/media/descargas_temporales` y el único destino
admisible es `<sandbox>/media/Peliculas` o `<sandbox>/media/Series`.

- Reutiliza un `OrganizationPlan` validado por el planificador, pero
  vuelve a comprobar que los destinos pertenecen al sandbox y
  la biblioteca seleccionada.
- Abre componentes de origen por descriptor con `O_NOFOLLOW` para
  rechazar enlaces simbólicos, y limita los archivos de prueba a **32 MiB**.
- Copia a una carpeta privada de *staging* con nombre vinculado al ID
  de descarga; utiliza creación exclusiva, nunca trunca un archivo preexistente.
- Comprueba tamaño, metadatos del origen y SHA-256 del contenido leído,
  vuelve a leer el origen y valida mediante SHA-256 los **bytes escritos
  realmente en destino**.
- Sincroniza ficheros/directorios y publica con
  `renameat2(RENAME_NOREPLACE)` en Linux. Rechaza una colisión que ocurra
  incluso justo antes de publicar.
- Si falla o se interrumpe, conserva los originales y **no borra ni
  reutiliza automáticamente el staging**; exige revisión.
- Esta primera prueba puede publicar un título nuevo de Películas o una
  carpeta nueva de serie con un único episodio y sus subtítulos.
  **No integra aún episodios en carpetas de series ya existentes**.

## Validaciones

- `backend/tests/test_organization_copy_sandbox.py`: **22 pruebas**
  exclusivas con `tmp_path`, incluyendo copia fiel, subtítulos,
  archivos falsificados, cambios en origen, symlinks, staging anterior,
  interrupción simulada, colisiones de mayúsculas, colisión simultánea
  con el destino y corrupción deliberada de la escritura.
- Suite backend completa: **397 pruebas aprobadas, 2 advertencias
  preexistentes de dependencias**.
- Ruff sin errores; `git diff --check` limpio.
- No se ha ejecutado esta implementación contra archivos del usuario.
  Las pruebas solo escriben en carpetas temporales de pytest.

## Por qué aún NO se activa en producción

Esta implementación **no es un organizador de medios operativo**:
carece de integración con `worker/main.py` y la cola `0013`;
no verifica por sí misma qBittorrent (hash, etiqueta y carpeta),
ni tiene heartbeat para archivos grandes o conciliación automática
tras una confirmación ambigua. El límite de 32 MiB es deliberado para
impedir que este prototipo se emplee como ejecutor real.

Antes de copiar medios auténticos faltan el aislamiento de escritura
mínima sobre el volumen Windows, permisos y espacio disponible, manejo
seguro de carpetas de series ya existentes, control de interrupciones,
lease y revalidación continua, recuperación sin duplicados y pruebas
con ficheros de demostración de tamaño realista. También es necesaria
una prueba de extremo a extremo con Jellyfin.

**Producción sigue en esquema 0012; no aplicar migración 0013 ni
activar organización o inicio automático de torrents.**

Referencias: [planificación](ORGANIZADOR-SEGURO-PLAN.md) y
[cola durable 0013](ORGANIZADOR-COLA-0013.md).
