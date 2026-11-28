# VIEWTV 0041 — barrera integrada de siete fuentes, control de coherencia temporal

**Fecha:** 28/11/2026. **Rama:** `viewtv-seguimiento-descargas-0012`, PR #2 OPEN/DRAFT. **Ámbito:** exclusivamente auditorías existentes de solo lectura + evaluación en memoria, sin instalación/despliegue ni cambios en servicios, Windows, SQL, qBittorrent o archivos multimedia.

## Problema y propósito

Los hitos 0018/0019/0026/0027/0033/0037/0040 ya exponen por separado preflight de película, prueba administrativa, custodia de todos los ficheros de torrents, superficie Jellyfin, puertos/firewall, identidades Windows y WebUI/GUI qBittorrent. Son observaciones parciales y temporales: aprobar cada informe por separado **no prueba que sus evidencias pertenezcan al mismo instante** ni impide cambios al terminar. Tampoco los estados `stop`, `loopback` o `contraseña configurada` son bloqueo kernel.

Se añade una única herramienta para **evaluar la coherencia de esas siete fuentes en ocho informes**. El 0018 se ejecuta antes y después para detectar parte de los cambios entre comprobaciones; la comparación exhaustiva falla cerrada ante cualquier diferencia visible. No se accede a IDs de películas desde argumentos ni se cruzan títulos, nombres de perfiles, hashes qBit, rutas, credenciales o URL firmadas en la salida del integrador.

## Implementación

- `worker/retirement_unified_gate_0041.py`: parser estricto en memoria para siete formatos, con claves obligatorias, campos opcionales permitidos por familia, ASCII, tamaños acotados, cero duplicados, números sin ceros a la izquierda y comprobación de ausencia de permisos o modificaciones. Rechaza cualquier origen que afirme autorizar borrar, que no declare explícitamente barreras pendientes o que no coincida con el contrato.
- Coherencia interna: exactamente tantas filas de películas bloqueadas como películas analizadas; ningún diario NTFS verificado adicional a los disponibles; número de candidatas administrativas menor o igual al de películas; número de torrents y estados compatible; **total de archivos publicados + extras protegidos igual a todos los archivos qBit**, desglose de categorías auxiliares consistente.
- Coherencia cruzada: igualdad estricta de **ambos preflight 0018** a inicio/final; mismo número de películas en 0018 y 0019; diarios NTFS registrados cubiertos por cantidad de archivos publicados correlacionados en 0026. **Comparar cantidades NO sustituye identidad exacta de torrent/hardlink bajo un lock**: la correlación identificativa real continúa siendo tarea del futuro ejecutor.
- `scripts/viewtv_retirada_interlock_0041.py`: invoca únicamente nombres **estáticos** de scripts existentes con `sys.executable -B`, sin argumentos, shell ni opciones de escritura. Tiempo máximo por fuente, respuesta en memoria y salida acotada; stderr suprimido al usuario. Realiza 0018 inicial, los seis restantes con un pool limitado a tres auditorías simultáneas, 0018 final. Imprime solo etiquetas categóricas, recuentos de fuentes y condiciones pendientes. Informe incompleto, ausente o contradictorio devuelve **código 2**; **ocho informes coherentes devuelven código 3 (BLOQUEADA)**. El proceso **NUNCA devuelve código 0**, para evitar que un automatismo confunda «auditoría completada» con «autorización de borrado». Siempre muestra cero autorizaciones y cero borrados.
- Toda evaluación retorna `estado=bloqueada`, `puede_retirar_archivos=False`, `permiso_de_borrado_otorgado=False`, incluso si los ocho informes fueran sintácticamente válidos y parecieran consistentes. La herramienta **no contiene operación de unlink, POST a qBit, administración ni mutación SQL** y no está conectada a servicios activos ni al ejecutor físico.

## Pruebas y evidencia

`backend/tests/test_retirement_unified_gate_0041.py`: **49/49 pruebas dirigidas PASS**. Prueban todas las fuentes válidas pero no autorizadoras, ocho casos de fuente ausente, recortes, permisos falsos, desaparición de filas, saltos de contadores, extras qBit omitidos, discrepancias 0018 inicial/final, recuento de películas 0019 contradictorio, diarios NTFS sin archivos qBit, infiltración de rutas/SID/API key, tipos no textuales, runner con fuente fallida y ausencia de argumentos arbitrarios.

**Ejecución real 0041: OCHO/OCHO informes VALIDADOS**, preflight 0018 al inicio y final coherentes, sin fallos ni contradicciones entre fuentes; `INTERLOCK_0041=SIETE_FUENTES_SOLO_LECTURA`, `ESTADO_RETIRADA_0041=BLOQUEADA`, seis barreras de producción declaradas `PENDIENTE`, permiso de borrado NO, 0 archivos eliminados y 0 torrents modificados. El comando Python termina con **código no cero incluso cuando las fuentes son coherentes** (contrato `return 3`); un informe incompleto devuelve 2. El lanzador externo puede normalizar códigos no cero, por lo que las pruebas unitarias verifican el código 3 de `main()`. Ninguna observación equivale a quietud productiva. **Ruff global PASS, TypeScript PASS, ESLint PASS y smoke real read-only 10/10 PASS**. **Regresión backend completa 1753/1753 PASS**, con 2 advertencias externas Starlette/FastAPI, ejecutada en Docker sin red con fuentes montadas solo lectura. Ruff global `backend worker scripts` PASS, TypeScript PASS, ESLint PASS, smoke real HTTP solo lectura 10/10 PASS y auditoría Windows/WSL 0041 de ocho informes concordantes. No se ha emitido ninguna orden qBit real ni realizado escritura NTFS.

## Por qué sigue prohibida la retirada

1. **Sin exclusión kernel NTFS real**, otro proceso podría crear un tercer hardlink o conservar escritor abierto (0034/0037).
2. **Sin custodia transaccional productiva de qBit**: 0038/0039 son laboratorios con `MockTransport`; la GUI, WebUI, reanudación tras reinicio y clientes de terceros siguen fuera del cerco (0040).
3. **Sin drenaje de Jellyfin directo/HLS v1**, HLS v2/admisión 0029–0032 no están desplegados; los puertos y firewall permiten potenciales accesos alternativos.
4. **Sin cuenta Windows broker y credencial administrativa independientes** ni aprobación específica de una película; las cuatro películas del último preflight seguían bloqueadas por perfiles, solicitudes, descargas y permisos.
5. **Sin ejecutor Windows durable** con identidades de File ID y comprobación de derechos en el instante exacto de la eliminación, diario protegido, prueba de recuperación tras apagón y medición de espacio realmente liberado.

**Esta barrera incrementa la detectabilidad de errores entre subsistemas, no instala todavía aislamiento ni habilita borrado.** No se modifican torrents, extras, Windows ACL, firewall, sesiones ni películas. PR #2 continúa en borrador.
