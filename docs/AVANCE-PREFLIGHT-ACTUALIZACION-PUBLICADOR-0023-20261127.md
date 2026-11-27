# VIEWTV 0023 — Verificación de actualización segura del publicador Windows

**Fecha:** viernes, 27 de noviembre de 2026 (Europe/Madrid).
**Repositorio:** `wizzadrds/viewtv`, **rama exclusiva** `viewtv-seguimiento-descargas-0012`.
**PR #2:** abierto, en borrador, sin fusionar.
**Prioridad:** terminar seguridad de espacio y retirada física antes de la app Samsung; «VIEWTV Momentos» después.

## Resumen

El código 0022 incorporó un mutex cooperativo Windows común para el publicador y la futura retirada, probado solo en aislamiento. **La instalación activa no se había actualizado**.

En 0023 se ha examinado **la configuración real del equipo Windows en modo estrictamente lectura** y se ha implementado una validación que rechaza una actualización automática mientras haya versiones diferentes, una tarea habilitada o información ambigua. También se ha ensayado con scripts reales **sin ejecutarlos** un cambio de versión y su recuperación en un sandbox GUID de Windows TEMP, incluyendo un corte simulado entre el script y el helper de mutex.

**No se ha detenido, deshabilitado, habilitado, sustituido ni reinstalado ninguna tarea o servicio productivo. No se ha cambiado ningún archivo de las películas, torrent, configuración del host, contenedor Docker o SQLite.**

## 1. Diagnóstico Windows real: bloqueo por estado

`scripts/viewtv_windows_publicador_upgrade_readonly_0023.ps1`

- Solo utiliza `Get-ScheduledTask`, `Get-Service`, `Get-CimInstance` y `Get-FileHash`, además de lecturas y comprobación de archivos/directorios sin reparse.
- Contrasta el hash SHA-256 del publicador instalado `C:\VIEWTV\publicador\bin\viewtv_windows_publicador_0013.ps1` contra la versión de la rama con mutex 0022.
- Comprueba si existe el helper `viewtv_windows_media_lock_0022.ps1` junto al script instalado, y compara su hash con el fuente.
- Compara también el wrapper de la tarea `viewtv_publicador_tarea_periodica_0013.ps1`, el nivel `Limited`, el inicio interactivo, la identidad y estado de la tarea, el registro del servicio SCM y las instancias PowerShell que podrían publicar.
- **Nunca muestra PID, usuario, command line, rutas particulares, hashes ni secretos**. Si alguna fuente falla, deniega la comprobación.
- Que no se observe ningún proceso no asegura que la tarea programada no inicie otro inmediatamente: este informe **jamás afirma exclusión productiva** ni autoriza la instalación.

Resultado observado:

```text
UPGRADE_0023=SOLO_LECTURA
PUBLICADOR_INSTALADO_COINCIDE_CON_FUENTE_0022=NO
HELPER_MUTEX_0022_INSTALADO=NO
HELPER_INSTALADO_COINCIDE_CON_FUENTE_0022=NO
TAREA_PROGRAMADA_CON_USUARIO_LIMITADO=SI
ACCION_TAREA_ES_ESPERADA=SI
WRAPPER_TAREA_COINCIDE_CON_FUENTE=SI
ESTADO_TAREA=READY
TAREA_EN_EJECUCION=NO
SERVICIO_SCM_EXISTE=NO
SERVICIO_SCM_ACTIVO=NO
PROCESOS_PUBLICADOR_OBSERVADOS=0
PROCESOS_POWERSHELL_SIN_LINEA_VISIBLE=0
VERSION_LISTA_PARA_REVISION_DE_MUTEX=NO
PUEDE_AFIRMARSE_EXCLUSION_PRODUCTIVA=NO
REEMPLAZO_AUTOMATICO_DESDE_AUDITORIA=NO
PROCESOS_DETENIDOS=0
TAREAS_MODIFICADAS=0
ARCHIVOS_MEDIA_MODIFICADOS=0
TORRENTS_MODIFICADOS=0
```

**Conclusión:** la tarea periódica está **habilitada (`READY`)**, ejecuta el wrapper esperado sin elevar privilegios y ningún proceso coincidía en el instante de consulta, pero el script instalado **es anterior al 0022** y **no tiene instalado el helper del mutex**. Por tanto, hay una ventana peligrosa para sustituir cualquiera de los dos archivos mientras la tarea aún puede arrancar automáticamente.

## 2. Barrera de mantenimiento con salida estrictamente saneada

- `worker/publication_upgrade_gate_0023.py`: función pura que acepta **exactamente** los campos esperados de Windows y rechaza claves inesperadas, valores ambiguos, conteos manipulados, informes duplicados, estados de tarea contradictorios o declaraciones de permisos/acciones realizadas.
- `scripts/viewtv_publicador_upgrade_preflight_0023.py`: inicia únicamente una instancia PowerShell con `-File` para la auditoría; captura su salida en memoria y expone recuentos y **motivos de bloqueo**, nunca nombres de personas, contraseñas, rutas, PIDs o hashes.
- Ninguna de estas funciones tiene capacidad de deshabilitar tareas, detener procesos, instalar scripts, autenticar al administrador, crear permisos de borrado ni modificar medios.

Salida real:

```text
UPGRADE_PUBLICADOR_0023=COMPROBADO_SOLO_LECTURA
BLOQUEOS_ACTUALES=4
BLOQUEO_BIBLIOTECA_MUTEX_NO_INSTALADA=SI
BLOQUEO_INSTALACION_NO_VALIDADA=SI
BLOQUEO_PUBLICADOR_INSTALADO_DESACTUALIZADO=SI
BLOQUEO_TAREA_NO_DESHABILITADA=SI
REEMPLAZO_AUTOMATICO=NO
PUBLICADOR_PRODUCTIVO_MODIFICADO=NO
TAREAS_MODIFICADAS=0
MEDIOS_MODIFICADOS=0
TORRENTS_MODIFICADOS=0
```

**Importante:** incluso si en otro momento los campos ya coincidieran y la tarea estuviera deshabilitada, la evaluación **nunca** devuelve permiso automático de actualización ni de eliminación física. Esta es solo una herramienta de preparación para una **intervención supervisada y autorizada**.

## 3. Ensayo de actualización y rollback entre procesos, sin producción

`scripts/viewtv_windows_publicador_upgrade_sandbox_0023.ps1`

- Crea un directorio nuevo `viewtv-upgrade-ficticio-0023-{GUID}` bajo TEMP, con marcador y estructura limitada `bin/stage/backup`.
- Fabrica un script de publicador **antiguo ficticio**. Copia a TEMP el código nuevo de **ambos ficheros reales del repositorio**, pero solo como datos, **sin ejecutarlos**.
- Verifica hashes SHA-256 de script y helper antes de intercambiar el contenido del **bin ficticio**.
- Crea un diario de intención con `FileMode.CreateNew`, `FileOptions.WriteThrough` y `Flush(true)`.
- Simula una interrupción **después** de `File.Replace` del script, pero **antes** de instalar el helper. Un segundo proceso PowerShell verifica identidad/huellas y restaura el script ficticio antiguo desde su backup. Se repite para demostrar que la recuperación es idempotente.
- Después completa la instalación ficticia de ambos archivos, comprueba hashes y realiza un rollback desde otro proceso, también dos veces para probar idempotencia.
- Limpia solo los nombres previamente conocidos en la carpeta GUID; nunca utiliza borrado recursivo y no recibe rutas productivas como parámetros.

Resultados:

```text
RECUPERACION_IDEMPOTENTE=PASS
RECUPERACION_IDEMPOTENTE=PASS
RECUPERACION_VERSION_INCOMPLETA_EN_OTRO_PROCESO=PASS
NUEVA_VERSION_Y_HELPER_FICTICIOS_SHA256=PASS
ROLLBACK_IDEMPOTENTE=PASS
ROLLBACK_IDEMPOTENTE=PASS
ROLLBACK_VERSION_OTRO_PROCESO=PASS
DIRECTORIO_SANDBOX_LIMPIADO=SI
TAREA_PRODUCTIVA_MODIFICADA=NO
PUBLICADOR_PRODUCTIVO_MODIFICADO=NO
MEDIOS_Y_TORRENTS_MODIFICADOS=0
```

Un primer ensayo encontró una incompatibilidad del argumento `null` para la ruta de backup de `File.Replace` en el PowerShell/.NET instalado. **Se corrigió en el sandbox** usando una ruta de backup explícita, se repitió el ensayo hasta completarlo y se limpió el directorio ficticio que dejó el intento interrumpido. `scripts/viewtv_windows_publicador_upgrade_cleanup_0023.ps1` solo elimina directorios bajo TEMP con prefijo y marca exactos, y solo si todos sus archivos y subdirectorios pertenecen a la lista permitida. Resultado del limpiador: **1 directorio ficticio limpiado, 0 rechazados**, cero datos reales modificados.

**Limitación:** esta prueba demuestra la mecánica de reemplazo/reversión de archivos en un directorio ficticio, no la quietud efectiva de la tarea programada productiva, las ACL del directorio de instalación real ni resistencia a un apagón real en el instante crítico. **No existe un instalador automático de producción en este hito.**

## 4. Validación, respaldo y estado productivo

- **48/48 pruebas nuevas** sobre contrato del informe y runner, con credenciales y estados completamente sintéticos. Incluyen pruebas de salida maliciosa, timeout, campos inesperados, tareas habilitadas y versiones incompatibles.
- Ruff **PASS**.
- Smoke existente **10/10 PASS**, sin sesión ni escrituras. **Suite backend completa 1269/1269 PASS**, con 2 advertencias de deprecación de dependencias externas; ejecutada en contenedor de pruebas sin red. Ruff PASS de los módulos Python de este hito.
- Copia previa de fuentes y documentación antes de crear los nuevos archivos:
  `/home/viewtv/viewtv-backups/publicador-upgrade-audit-pre-20261127-164257.tar.gz`
  SHA-256 `88bd1073cc2531b56ae0bdca4172f2e55e0fad91061ea7d86d8b9732e831b75e`; `tar -tzf` verificado.
- No se guardaron secretos ni ficheros de vídeo en el backup. No se creó otro respaldo de bases SQLite porque **no se modificó su esquema ni contenido**.
- Preflight real 0018/0019 final: **4/4 películas bloqueadas**, **2 diarios NTFS verificados**, 2 torrents aún activos o incompletos según la política de retirada, 4 películas sin marcas «vista» suficientes, **3 con motivo «sin solicitud válida»**, 0 candidatas para autorización administrativa, 0 aprobaciones emitidas, 0 archivos o torrents modificados. Esta cifra de tres difiere de la observada en el hito anterior; no se han cambiado solicitudes durante la auditoría y nunca se infiere autorización de esos cambios.
- Productivo sin cambios: API/frontend de caché 0017, worker 0015, Jellyfin y catálogo existentes. El publicador programado sigue con el script instalado antiguo.

## 5. Procedimiento para la siguiente fase, **no ejecutado**

**No se deben interpretar los siguientes pasos como una autorización actual para intervenir.** Requieren un administrador de Windows y una ventana de mantenimiento supervisada, con posibilidad de recuperación:

1. Inventariar la tarea, su cuenta limitada y los ficheros instalados; respaldar **el script del publicador instalado**, el wrapper, el helper si existiera, permisos ACL, la definición y estado de la tarea y el diario de publicaciones. Verificar SHA-256 de cada archivo y mantener respaldo privado y restaurable.
2. Obtener autorización del administrador para deshabilitar temporalmente la tarea programada. Confirmar **en dos instantes diferentes** que no queda ningún proceso publicador ni trabajos en staging/claim/confirm y que la ventana de ejecución de tarea ha quedado cerrada. El estado `READY` actual **no garantiza inactividad continua**.
3. Con la tarea realmente deshabilitada y la exclusión garantizada, preparar **script y helper como un conjunto inseparable**, con los permisos limitados del directorio Windows. Rechazar reemplazos parciales, archivos reparse, hashes diferentes o permisos heredados inesperados.
4. Realizar el cambio de archivos con respaldo y fases registradas; después comprobar que el par instalado coincide con los hashes aprobados. Si una fase falla, con la tarea aún deshabilitada, restaurar el backup verificado.
5. Ejecutar **solo preflight de lectura** del publicador y comprobar el mutex con el proceso instalado. Validar que las políticas Windows/API permanecen en `general`, `after_id=3` y no se han modificado las descargas previas.
6. Solo tras decisión administrativa supervisada, reactivar la tarea. Comprobar que hay **una única autoridad publicadora**, que mantiene el mutex antes de procesar y que no crea colisiones ni reproduce trabajos anteriores.
7. Mantener **prohibido** el borrado de películas: el mutex no protege procesos de qBittorrent ni nuevas reproducciones en Jellyfin, ni sustituye consentimiento por película, preflight técnico, control de perfiles y diario durable de retirada.

**Orden del proyecto:** acabar gestión física de espacio y retirada segura → app profesional Samsung Tizen → «VIEWTV Momentos».
