# VIEWTV 0020 — Origen qBit completo y diario de retirada recuperable (sandbox)

**Fecha:** jueves 26 de noviembre de 2026 (Europa/Madrid).
**Rama:** `viewtv-seguimiento-descargas-0012`; repositorio `wizzadrds/viewtv`; PR #2 **OPEN/DRAFT, NO MERGE**.
**Prioridad acordada:** terminar eliminación física segura y espacio/caché antes de la app Samsung; «VIEWTV Momentos» después.

## Resumen

Se han dado dos pasos concretos hacia la retirada física: **se ha identificado la clase de los cuatro archivos de qBittorrent que no estaban en los diarios de publicación** y se ha ensayado en Windows **un diario write-through de retirada de hardlinks, recuperable por otro proceso y repetible de forma segura**.

**No se ha desplegado un ejecutor de producción, creado una credencial administrativa real ni activado la eliminación desde la web. Cero películas reales y cero torrents modificados.**

## A. Inventario de qBit: diagnóstico exacto solo lectura

Código:
- `worker/retirement_inventory_0020.py`: función pura para clasificar inventarios sin autorizar borrados; nombres, rutas e infohash quedan en memoria y el resultado contiene solo totales.
- `scripts/viewtv_retirada_inventario_0020.py`: consulta por GET a través de la API local `viewtv-api-1` y compara con diarios de publicación existentes leídos con `O_NOFOLLOW`. **No hay endpoints ni métodos de escritura de qBit.**
- `backend/tests/test_retirada_inventario_0020.py`: datos de sandbox; detecta archivos extras, incoherencias de tamaño, tipos de archivos, ficheros desconocidos, nombres reservados, repetidos y errores de origen, sin producir permisos.

Resultado real de la consulta:

```text
INVENTARIO_0020=SOLO_LECTURA
DESCARGAS_ANALIZADAS=2
ARCHIVOS_QBIT=6
ARCHIVOS_PUBLICADOS_CORRELACIONADOS=2
ARCHIVOS_NO_PUBLICADOS_PROTEGIDOS=4
EXTRA_TIPO_METADATO=4
NO_NORMALIZABLES=2
SUMA_BYTES_LOGICOS_NO_PUBLICADOS=488
TAMANOS_INCOMPATIBLES=0
QBIT_NO_DISPONIBLE=0
TAMANO_LOGICO_NO_ES_ESPACIO_LIBERABLE=SI
ARCHIVOS_ELIMINADOS=0
TORRENTS_MODIFICADOS=0
```

**Interpretación:** los cuatro extras tienen extensiones de **metadatos**, no de vídeo, y en conjunto suman **488 bytes lógicos**. Los dos nombres no normalizables no se corrigen ni ignoran: **se mantienen las restricciones de seguridad**. Es un inventario, **no prueba que los extras pertenezcan exclusivamente a VIEWTV ni autoriza borrarlos**. Los dos originales y sus torrents siguen asociados a descargas que no cumplen la política de retirada (activos en las últimas consultas). La coincidencia de tamaño de los dos publicados es exacta.

**La suma lógica de 488 bytes NO equivale a bloques NTFS liberables.** Los metadatos no se borraron ni movieron; el preflight 0018/0019 permanece cerrado para los dos torrents activos y todas las películas sin marcas/peticiones válidas.

## B. Diario de retirada en Windows: ensayo recuperable

Archivo exclusivo: `scripts/viewtv_windows_retirada_diario_sandbox_0020.ps1`.

- El modo `Test` crea **solo** una carpeta nueva `viewtv-0020-ficticio-{GUID}` bajo el directorio TEMP local; usa nombres constantes de **dos archivos ficticios** (original/publicado, mismo inode NTFS) y datos sintéticos de 1 MiB. No acepta rutas de usuario ni operaciones de producción.
- Verifica marca del sandbox, estructura limitada, ausencia de entradas redirigidas, identidad NTFS por volumen, índice, tamaño y exactamente dos hardlinks. Reutiliza funciones verificadas de la auditoría real 0016, que solo lee `C:\VIEWTV\media`.
- Crea diarios `01-intent`, `02-restored`, `03-finalize-intent`, `04-unlinked` y `05-finished` con `FileMode.CreateNew`, `FileOptions.WriteThrough` y `Flush(true)`, antes/después de fases críticas. La firma de identidad del archivo queda registrada en cada fase.
- Simula una interrupción **después de eliminar únicamente la copia publicada ficticia, pero antes de escribir el diario de resultado**. Inicia **otro proceso powershell.exe** con modo privado `Recover`; este recupera el hardlink desde el original conservado y deja registrada la restauración.
- Ejecuta de nuevo `Recover` para confirmar **idempotencia**: si la recuperación ya terminó, comprueba el diario y los dos enlaces, sin duplicar operaciones.
- En otro proceso `Finish` registra la intención de finalizar **antes de borrar**; elimina ambos enlaces **exclusivamente sintéticos**, dejando huellas y fases; vuelve a ejecutarlo y verifica que la finalización repetida no modifica nada.
- El proceso principal verifica que no queda ningún enlace ficticio, elimina únicamente sus propios diarios y marca del directorio GUID, y elimina el directorio vacío con `Directory.Delete(root,false)`, sin borrado recursivo.
- **Nunca ejecuta operaciones de borrado en `C:\VIEWTV\media`, ni modifica Jellyfin, qBittorrent, torrents, base de datos o medios.**

Resultado de Windows:

```text
RECUPERACION_EN_PROCESO_WINDOWS_DISTINTO=PASS
RECUPERACION_EN_PROCESO_WINDOWS_DISTINTO=PASS
DIARIO_WRITETHROUGH_Y_RESTAURACION_POST_CORTE=PASS
DIARIO_DE_FINALIZACION_FICTICIA=PASS
FINALIZACION_REPETIDA_SIN_OPERACIONES=PASS
AMBOS_HARDLINKS_FICTICIOS_RETIRADOS=PASS
DIRECTORIO_FICTICIO_LIMPIADO=SI
PELICULAS_REALES_BORRADAS=0
TORRENTS_REALES_MODIFICADOS=0
```

**Límites del ensayo:** simula una caída entre procesos, no un apagón físico real. El diario no tiene todavía firma autenticada de aprobación administrativa, reserva con el publicador, bloqueo de streams de Jellyfin, bloqueo real de qBit, medición de clusters físicos liberados ni política de revocación. La escritura write-through reduce el riesgo de pérdida de información, pero no permite afirmar recuperabilidad garantizada ante cualquier apagón o daño de disco. Es un **laboratorio**, no una utilidad de eliminación para películas reales.

## C. Comprobaciones, respaldo, despliegue

- Respaldo de código y documentación pre-0020:
  `/home/viewtv/viewtv-backups/retiro-sandbox-inventario-pre-20261126-204038.tar.gz`,
  SHA-256 `159071ae20120c6c04e5c083a330c7e142f6407b971bd914fd399196efc5a137`.
  Verificado con `sha256sum` y `tar -tzf`. No contiene `.env`, claves administrativas, bases de datos, torrents, archivos multimedia ni copias de Windows.
- Pruebas puras del inventario: **11/11 PASS**; Ruff PASS.
- Suite completa del backend **1159/1159 PASS**, con 2 advertencias de deprecación de dependencias externas; ejecutada en contenedor de pruebas sin acceso de red.
- Smoke de solo lectura de API/web/Jellyfin: **10/10 PASS**; publicador de Windows `status` respondió `listo`. Auditoría NTFS Windows posterior: **2/2 diarios verificados, 0 bloqueados, 1 carpeta sin diario conservada y 0 eliminaciones reales**.
- Sin migración SQLite ni contenedor actualizado en este hito; siguen API `viewtv:cache-propia-api-0017`, frontend `viewtv-frontend:cache-propia-0017`, worker `viewtv:gestion-espacio-worker-0015` y Jellyfin anterior.
- Rama, push y PR #2 se comprueban tras el commit.

## D. Requisitos de la próxima fase (antes de Samsung)

1. Alta real del administrador de biblioteca y custodia segura de la clave (el módulo 0019 es solo prototipo offline); aprobación por **una sola película** y aceptación informada de que desaparece para todos los perfiles.
2. Establecer la política de protección o conservación de metadatos qBit extras: que sean pequeños no autoriza a borrarlos; no usar su clasificación para saltar las barreras del preflight.
3. Control de concurrencia **real** con el publicador Windows, streams/lector de Jellyfin y estado qBit; abortar si el torrent está activo, compartido o cambia entre pruebas.
4. Ejecutar la retirada física **exclusivamente mediante autoridad Windows aislada**, tras revalidar misma evidencia y ticket consumido con bloqueo. Registro completo durable, ensayo de fallos físicos parciales, límites de tiempo y revocación.
5. Medición con API de espacio libre NTFS antes/después y atribución real de liberación; distinguir tamaños lógicos de hardlinks compartidos.
6. Conectar productores propios futuros a la caché privada 0017, sin tocar Jellyfin ni originales de torrents.

**Orden:** seguridad y gestión de espacio → app Samsung Tizen instalable profesional → «VIEWTV Momentos». **No empezar la app Samsung todavía.**
