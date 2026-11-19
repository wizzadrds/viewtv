# VIEWTV — Identidad de torrents antes de organizar archivos

**Estado: desarrollo 0013, solo lectura y simulaciones. No desplegado.**
Fecha: 19-11-2026.

## Objetivo

El organizador debe descartar cualquier torrent que no sea
**exactamente la descarga de VIEWTV que reclama**, incluida la
descarga preexistente ajena conservada en el qBittorrent de Windows.

El módulo `worker/organization_torrent_guard.py` añade
`verify_organization_torrent_identity`. Recibe un registro de
`Descarga` de VIEWTV, un cliente qBittorrent y una raíz de archivos.

## Validaciones realizadas

Antes de consultar al gestor:
- Identificador de descarga válido.
- Estado `completada`, progreso 100 %, verificación
  `verificada` y fecha de verificación registrada.
- Organización `pendiente`.
- Hash qBittorrent de 40 o 64 caracteres hexadecimales.

En la **primera consulta GET** (`torrents/info`) exige:
- Una y solo una respuesta coincidente con ese hash.
- Etiqueta exacta `viewtv-descarga-{id}`. Rechaza la ausencia,
  duplicación o una segunda etiqueta `viewtv-descarga-*` de otro
  trabajo. Puede coexistir una etiqueta adicional no propietaria.
- Estado de torrent completado y verificable, según la lista de
  estados conservadores del verificador actual.
- Carpeta de guardado exacta `C:\VIEWTV\media\descargas_temporales`
  en formato Windows, sin permitir bibliotecas ni rutas alternativas.

Solo tras superar lo anterior consulta los archivos con
**GET `torrents/files`** y reutiliza `validate_torrent_files`:
- Nombres y rutas relativas seguras, prioridad positiva,
  progreso completo, tamaños válidos, total consistente,
  ausencia de enlaces simbólicos y confinamiento a la raíz.
- Archivos existentes de tamaño esperado.
- Devuelve exclusivamente los `Path` comprobados.

**No existe ningún POST, orden de inicio/pausa, cambio de etiquetas ni
modificación de archivos en este módulo.**

## Pruebas

- `backend/tests/test_organization_torrent_guard.py`: **45 casos**
  con clientes simulados: propietario correcto, etiquetas ajenas,
  hash equivocado, duplicados, estado o carpeta incorrectos, archivo
  modificado, ruta traviesa, symlink y fallo de comunicación.
- Integración de demostración con
  `worker/organization_runner_sandbox.py`: **4 casos adicionales**:
  torrent propio se organiza dentro de `/tmp`; etiqueta de otro trabajo
  y ruta no autorizizada se bloquean; error de comunicación previo a
  cualquier escritura se aplaza con código seguro.
- Las pruebas no consultan el qBittorrent de Windows ni tocan torrents.
- **Suite backend completa: 471 pruebas aprobadas, 2 advertencias
  conocidas de dependencias**. Ruff limpio y revisión de espacios correcta.

## Qué falta antes de la organización real

- Conectar una variante de este guard a un ejecutor de producción
  **solo tras definir autorización, permisos y confinamiento de
  escritura**. El runner actual sigue limitado a sandbox bajo `/tmp`.
- Comprobar de nuevo identidad, archivo y lease justo antes de publicar.
- Definir política sobre archivos grandes, cambios durante copia,
  escaneos de Jellyfin, colisiones y carpetas de series existentes.
- Ensayar con contenido de redistribución autorizada y una biblioteca
  completamente aislada antes de habilitar las rutas Windows reales.
- Copia nueva de producción y ensayo de migración/rollback `0013`;
  mantener banderas de inicio automático y organización desactivadas.

**No ejecutar esta fase contra el torrent ajeno ni activar el
organizador del worker todavía.** Producción permanece en 0012.

Documentos relacionados: [cola 0013](ORGANIZADOR-COLA-0013.md)
y [orquestación sandbox](ORGANIZADOR-ORQUESTACION-SANDBOX.md).
