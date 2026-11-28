# VIEWTV 0049 — nonce durable y antirrepetición tras caída Windows (solo TEMP)

**28/11/2026.** Rama `viewtv-seguimiento-descargas-0012`, PR #2 abierta y en borrador, sin merge ni despliegue. Ningún servicio o ACL de producción, credencial, torrent ni película ha sido modificado.

## Problema y alcance

El 0048 ya comprobó el SID del cliente IPC mediante `RunAsClient` del servidor Windows y rechazó órdenes ficticias repetidas. Sin embargo, su `HashSet` de nonces vive **solamente en memoria**: si el servidor muere, la misma petición podría aceptarse tras reiniciar. Este 0049 ensaya una **bitácora NTFS privada de nonces reservados y confirmados en disco ANTES de cualquier efecto mock**. Sigue siendo una demostración independiente: **NO está conectado al pipe 0048 ni a un broker real**.

## Implementación

`scripts/test_viewtv_windows_pipe_nonce_durable_sandbox_0049.ps1` únicamente crea archivos ficticios `intencion-<nonce>.txt` en `TEMP/viewtv-0049-ficticio-<guid>`, con GUID aleatorio de la ejecución, marca estricta de propiedad y un conjunto cerrado de nombres válidos. Los subprocesos aceptan solo `RunId` hexadecimal válido y modos predefinidos (`CrashA`, `ReplayA`, `DifferentA`, `ReserveB`, `ReplayB`, `RaceC`, `CorruptD`). **No hay argumentos de rutas, nombres de películas, hashes qBit reales ni servicios.** Se rechazan reparse points en TEMP, directorio, marcador y archivos observados.

Cada intención incluye una operación mock, hash sintético, nonce del sandbox y huella SHA256 del SID del usuario del ensayo. Se crea con `FileMode.CreateNew` (exclusión atómica del nombre), `FileOptions.WriteThrough` y `Flush(true)` **antes** de devolver `RESERVADO_MOCK`. No se reenvía ni se ejecuta un START real. Si existe la intención, una segunda petición se deniega; si su contenido no coincide, también se deniega. No hay TTL ni rearmado automático.

- Un proceso Windows hijo se mata realmente mediante `TerminateProcess(GetCurrentProcess(),89)` después de escribir y confirmar el primer registro. Otro proceso recupera el mismo sandbox y **rechaza el nonce anterior**.
- El mismo nonce con otro hash se deniega, sin reescritura del registro.
- Un nonce distinto puede reservarse una vez; una segunda vez se deniega.
- Cuatro procesos Windows compiten por otro nonce nuevo: **exactamente uno** obtiene `FileMode.CreateNew` y los otros tres deben ser denegados. Si ven el fichero mientras el ganador aún lo está escribiendo, pueden recibir `DENEGADO_INTEGRIDAD`, que también es rechazo seguro. Tras salir todos, se compara además el contenido completo del registro final con el esperado.
- Un registro deliberadamente corrupto se deniega; ningún proceso lo repara o elimina automáticamente.

El ensayo elimina solamente sus archivos ficticios explícitamente permitidos y su carpeta GUID no recursivamente, y emite 12 líneas categóricas. `scripts/viewtv_windows_nonce_cleanup_sandbox_0049.ps1` es un limpiador separado sin parámetros para restos **únicamente** de este mismo ensayo en Windows TEMP: exige que el nombre sea un GUID, marcador exacto, lista de nombres cerrada, sin enlaces de directorio/reparse points, y usa `File.Delete`/ `Directory.Delete(...,false)` únicamente en ese espacio.

`worker/retirement_nonce_durable_gate_0049.py` valida exactamente las 12 líneas del reporte y deniega cualquier añadido, suplantación o afirmación de permiso. `scripts/viewtv_retirada_nonce_0049.py` ejecuta **dos pruebas Windows independientes** desde WSL, no admite argumentos arbitrarios, captura solo el reporte limitado y **nunca devuelve código 0**: 3 si ambas fuentes son válidas pero retirada bloqueada, 2 si alguna fuente es inválida.

## Resultados y corrección de una carrera real

La ejecución directa inicial pasó. La primera comprobación dual detectó una ejecución no verificable: los procesos perdedores de la carrera podían ver el fichero creado pero aún en proceso de escritura y devolver `DENEGADO_INTEGRIDAD`, mientras el test solo esperaba `DENEGADO_REPLAY`. El comportamiento real **fue denegar**, no conceder una segunda reserva. Se corrigió el criterio: exige **un único `RESERVADO_MOCK`**, tres denegaciones de cualquiera de ambos tipos y, después, **la huella/cadena completa correcta** del registro final. La prueba completa corregida en Windows consiguió **2/2 informes válidos**.

El limpiador estrictamente limitado a TEMP confirmó `SANDBOX_0049_PROPIOS_LIMPIADOS=2`, `ARCHIVOS_DE_MEDIOS_ELIMINADOS=0`, `TORRENTS_MODIFICADOS=0` para los restos de los ensayos interrumpidos. `backend/tests/test_retirement_nonce_durable_gate_0049.py`: **54/54 pruebas nuevas PASS**. Ruff global PASS. La ejecución WSL mostró `ESTADO_RETIRADA_0049=BLOQUEADA`, `AUDITORIAS_VALIDAS=2`, `PERMISO_DE_BORRADO_OTORGADO=NO`, 0 archivos reales eliminados y 0 torrents modificados.

**Regresión completa validada:** **2.003/2.003 pruebas backend PASS**, 2 advertencias externas Starlette/FastAPI, Docker sin red y repositorio montado solo lectura; **Ruff global** `backend worker scripts` PASS; **TypeScript PASS, ESLint PASS**; smoke HTTP real de solo lectura **10/10 PASS**. Preflight 0018: **4/4 películas BLOQUEADAS, 2/2 diarios NTFS válidos**; custodia qBit 0026: **2 torrents sin reposo seguro, 4 archivos auxiliares protegidos, 488 bytes lógicos**; interlock real 0041: **8/8 informes coherentes, seis barreras PENDIENTES y permiso físico NO**, cero borrados y cero cambios de torrents.

## Qué falta y por qué sigue prohibido borrar

La demostración `FileMode.CreateNew` + `WriteThrough` + `Flush(true)` **no equivale a probar resistencia a una caída eléctrica de todo el volumen ni sincronización durable de sus metadatos de directorio**. Sus directorios TEMP heredan la seguridad del operador del ensayo y pueden ser accesibles por otros procesos con el mismo SID. Tampoco hay un broker IPC con SID de servicio diferente, límite de lectura de frames integrado, autenticación end-to-end durable, ni posibilidad de exigir al qBit real que todos los accesos GUI/WebUI pasen por esta bitácora. El módulo de 0048 sigue teniendo nonces exclusivamente en RAM. No se ha realizado ni fingido dicha integración.

Permanecen abiertas la exclusión kernel NTFS por File ID y SID independiente; protección contra terceros hardlinks y lectores Jellyfin/HLS; control exclusivo de reanudaciones de qBittorrent; autorización administrativa individual de una película vista por **todos** los perfiles y apta en el preflight; ejecutor y recuperación de producción; y medición del espacio físico liberado. Sin aprobación explícita de mantenimiento no se modificarán cuentas, claves, puertos, servicios, ACL o torrents activos.

**Estado: laboratorio 0049 completado; borrado de medios productivos BLOQUEADO.**