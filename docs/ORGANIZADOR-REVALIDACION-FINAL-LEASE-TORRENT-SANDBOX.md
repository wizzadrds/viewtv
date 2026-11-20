# VIEWTV 0013 — revalidación estricta justo antes de los dos movimientos NTFS

Fecha: 20-11-2026. Rama: `viewtv-seguimiento-descargas-0012`.
**HITO DE LABORATORIO, NO AUTORIZA DESPLIEGUE NI PUBLICACIÓN REAL.**

## Riesgo abordado

La modalidad anterior de admisión por pipe v3 consulta un lease de
una SQLite ficticia y un torrent HTTP ficticio antes de crear
reservas. Estas consultas eran demasiado tempranas para decidir si
era seguro realizar después una publicación NTFS: el lease podía
caducar o el torrent cambiar de estado entre ambas acciones.

Se ha añadido una modalidad **optativa y explícitamente experimental**
al publicador del sandbox, con `-BrokerHandoff
-RequireFinalSandboxAuthority`. El código lee una configuración
anclada en el directorio privado del broker, y **vuelve a comprobar
ambas autoridades** antes del primer `Directory.Move` y otra vez
justo antes del segundo. No se pasan la URL del origen ni la ruta
SQLite desde la solicitud de copia.

**Los modos históricos siguen siendo ejecutables sin este switch
para conservar las regresiones de sandbox. Por tanto NO es todavía
una política obligatoria para todas las vías de publicación.**

## Archivos y modificaciones

- Nuevo: `scripts/viewtv_windows_final_gate_sandbox.ps1`.
  Expone `Assert-ViewtvSandboxFinalGate`, un control exclusivamente
  de lectura sobre configuraciones/SQLite/HTTP.
- Editado: `scripts/viewtv_windows_broker_handoff_sandbox.ps1`.
  Revalida el doble gate una vez confirmados aprobación firmada,
  ACL y quiescencia, inmediatamente antes del primer rename.
  Tras la entrega privada, repite el gate inmediatamente antes
  de renombrar el escrow al destino. Si el segundo gate falla,
  **conserva el escrow**; no libera automáticamente el trabajo.
- Editado: `scripts/viewtv_windows_publish_sandbox.ps1`.
  Añade `-RequireFinalSandboxAuthority`, permitido solo junto
  con `-BrokerHandoff`; en modo histórico directo lo rechaza.
- Nuevo: `scripts/test_viewtv_windows_premove_double_gate_sandbox.ps1`.
  Usa un GUID único bajo `C:\Users\Public`, marcador explícito,
  una cámara privada con ACL estricta, aprobación HMAC, SQLite
  sintética WSL y servicio HTTP ficticio solo en loopback.

## Registro privado de autoridad final

Ruta fija:
`C:\Users\Public\viewtv-win-sandbox-<GUID>\
.viewtv-broker-handoff\.viewtv-final-authority.json`

El archivo de prueba se crea con:
- Propietario BUILTIN\Administrators, DACL protegida y ACE
  exclusivamente para SID del broker ejecutante, SYSTEM y
  Administrators, con FullControl; se rechazan Users, ACE ajenas,
  heredadas o repetidas y enlaces/reparse.
- JSON canónico que incluye versión, GUID del sandbox,
  SID del broker, staging, destino, download_id, attempt, worker,
  torrent_hash, SHA-256 del **payload de la aprobación HMAC**
  existente, ruta de SQLite de prueba, URL HTTP de prueba y caducidad.
- Validación de tipos, campos, formato, longitud, ventana de
  expiración y coincidencia exacta con la publicación en curso.
  El SHA-256 no es una firma independiente: se vincula a la
  autorización HMAC ya verificada previamente por el publicador.
- Prohibición de directorios fuera del sandbox, URL distinta de
  `http://127.0.0.1:<puerto-alto>` y rutas SQLite distintas de
  `/tmp/viewtv-lease-gate-<GUID>/organization.sqlite3`.

Solo después invoca los guardas previos de **lease vigente** y
**torrent ficticio de la misma descarga, GUID y hash**. El segundo
control vuelve a leer el registro y las fuentes; no se conforma
con reutilizar un resultado anterior.

## Pruebas observadas

Prueba de publicación/revalidación:
`test_viewtv_windows_premove_double_gate_sandbox.ps1` —
**9 comprobaciones correctas**, exit code 0 (12,79 s) en la
última ejecución.

| Caso | Resultado |
|---|---|
| Solicitar control estricto sin handoff | Rechazado |
| Solicitar handoff estricto sin configuración privada | Rechazado antes de mover |
| SID del broker registrado incorrecto | Rechazado |
| Hash del plan firmado diferente | Rechazado |
| Configuración final con ACE de grupo Users | Rechazado |
| Torrent con etiqueta de otra descarga antes del primer move | Rechazado, staging intacto |
| Lease y torrent válidos | Dos renames y publicación **sintética** |
| Torrent incompleto en escrow simulado | Rechazo, escrow conservado |
| Lease caducado en escrow simulado | Rechazo, escrow conservado |

**Precisión de la prueba:** el cambio de estado *después* de la
entrega se inyectó en un escrow creado por el test, que invoca
el mismo `Assert-ViewtvSandboxFinalGate` que usa el publicador.
No se ha conseguido provocar todavía una caída real y determinista
entre los dos renames dentro de la misma ejecución del publicador.
No interpretar esos dos últimos casos como una prueba de crash real.

Regresiones ejecutadas:
- `test_viewtv_windows_broker_handoff_sandbox.ps1`: **14 correctas**.
- `test_viewtv_windows_publish_sandbox.ps1`: **20 correctas**.
- `test_viewtv_windows_restricted_acl_sandbox.ps1`: **29 correctas**.
- `test_viewtv_windows_pipe_dual_gate_sandbox.ps1`:
  **22 comprobaciones correctas**, exit code 0 (38,61 s).
- Backend completo en Ubuntu: **615 passed, 2 warnings**
  de deprecación conocidos, exit code 0 (44,12 s),
  ejecución sin caché ni bytecode.
- Parser de PowerShell 5.1 de los cuatro scripts nuevos/editados: correcto.

En el primer test se verificó la eliminación de la SQLite temporal,
el HTTP falso, el diario/clave temporal y la carpeta de pruebas
sin tocar ninguna ruta fuera de los GUID creados por el ensayo.

## Copia de seguridad anterior a editar los archivos existentes

`/home/viewtv/viewtv-backups/pre-move-doble-gate-pre-20261120-162126.tar.gz`

SHA-256:
`75facd50d433057f5e06d2feba19ade652b4676d1fc74c79b62d929ac999b037`

`tar -tzf` confirmó exactamente:
- `scripts/viewtv_windows_broker_handoff_sandbox.ps1`
- `scripts/viewtv_windows_publish_sandbox.ps1`
- `docs/ORGANIZADOR-DOBLE-GATE-LEASE-TORRENT-PIPE-SANDBOX.md`

Los dos nuevos scripts de esta iteración y el informe
no tenían versión previa que respaldar.

## Riesgos y trabajo pendiente — fase 1 NO cerrada

1. **Vía opcional:** el modo histórico todavía publica archivos
   ficticios sin doble gate. Para producción deberá eliminarse
   cualquier ruta de publicación que no exija la misma política.
2. **Configuración creada por el laboratorio:** aún no hay un
   registro de autoridad emitido por un servicio broker persistente
   con cuenta Windows no administrativa e independencia del worker.
   Una cuenta administradora hostil puede alterar el registro.
3. **Actualización posterior:** la modalidad estricta ahora
   exige dos reservas durables del canal de admisión v3 en un diario
   GUID privado, cotejadas con el nonce y hash del plan HMAC,
   download_id, worker, intento, staging, destino y torrent.
   La integración se probó mediante el pipe real de sandbox.
   Véase [ORGANIZADOR-RESERVA-V3-VINCULADA-PUBLICACION-SANDBOX.md](ORGANIZADOR-RESERVA-V3-VINCULADA-PUBLICACION-SANDBOX.md).
   **Sigue faltando un journal global independiente**, protección
   ante administradores hostiles y reconciliación real.
4. **Origen externo no transaccional:** una consulta HTTP y otra
   SQLite pueden cambiar después de la validación y antes de
   Directory.Move. No se ha cerrado completamente TOCTOU, ni
   probado un cierre hostil, archivos multigiB o crash de broker.
5. Sigue faltando reconciliación real entre journal, NTFS, SQLite
   y estado de qBittorrent. Nunca auto-reintentar si ya existe
   escrow/final ambiguo.
6. Solo se usa SQL ficticia y servidor HTTP marcado; no se
   consultan torrents reales ni se modifica `C:\VIEWTV\media`.
   Mantener `VIEWTV_ENABLE_DOWNLOAD_START=false`.
7. API 0012 sigue reiniciándose por discrepancia de imágenes /
   revisiones de migración; exige otro hito de reparación,
   respaldo consistente y aprobación antes de actuar.
8. PR #2 mantiene estado borrador; no fusionar ni desplegar.

**Decisión:** control pre-move doble probado en modo estricto
experimental; fase 1 aún abierta, sin impacto productivo.
