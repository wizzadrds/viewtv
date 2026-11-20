# VIEWTV 0013 — SID del copiador anclado al broker (sandbox NTFS)

Fecha: 20-11-2026. Rama única: viewtv-seguimiento-descargas-0012.
**Estado: prototipo de laboratorio, nunca producción.**
No se crean servicios, no se toca C:\VIEWTV\media, ni SQLite real,
qBittorrent, Jellyfin, .env o PIN.

## Amenaza cubierta en esta iteración

El guard de ACL del hito anterior podía ser engañado si el cliente
entregaba un SID incorrecto en el argumento -CopySid: las ACL de un
copiador diferente quedarían sin comprobar.

Se eliminan -CopySid y -BrokerSid del punto de entrada
scripts/viewtv_windows_publish_sandbox.ps1. Cuando se usa
-BrokerHandoff, el publicador lee SIEMPRE el SID de copia de un
archivo de identidad de ruta fija en la cámara privada del broker.
El cliente no puede elegir la ruta ni el SID en los parámetros.

Código nuevo:
scripts/viewtv_windows_pinned_identity_sandbox.ps1
Función: Get-ViewtvSandboxPinnedCopySid.

Ruta exacta permitida:
C:\Users\Public\viewtv-win-sandbox-<GUID>\
  .viewtv-broker-handoff\.viewtv-copy-identity.json

El registro, creado exclusivamente por el inicializador de la prueba,
contiene version=1, sandbox, copy_sid, broker_sid y expires_utc.
No contiene contraseñas. El JSON es canónico y compacto;
se rechazan campos inesperados, duplicados, estructura distinta,
identidades incorrectas y caducidad fuera de la ventana permitida.

## Garantías observables del lector

1. El sandbox debe tener GUID, marcador y ruta directamente bajo
   C:\Users\Public; se rechazan cruces y reparse points.
2. El directorio privado debe tener propietario Administradores,
   DACL protegida y EXACTAMENTE tres ACE FullControl para SYSTEM,
   Administradores y el SID que está ejecutando el lector. Se rechazan
   grupos como Users, ACE heredadas, duplicadas y denegaciones.
3. El archivo fijo debe existir, ser regular, no ser reparse, tener
   tamaño de 100 a 1024 bytes, propietario Administradores, DACL
   protegida y exactamente las mismas tres ACE FullControl.
4. El broker_sid inscrito debe coincidir con la identidad del
   proceso lector (WindowsIdentity.GetCurrent().User.Value).
5. El SID copiador debe ser distinto al del broker y a la identidad
   del proceso. Se rechazan formatos incorrectos, SYSTEM y
   Administradores, y registros caducados o con vigencia superior
   a una hora.
6. El cuerpo debe coincidir exactamente con su serialización JSON
   canónica; una modificación ambigüa no se acepta.
7. Se revalida la DACL privada también frente al SID leído.
8. El publicador vuelve a leer el registro después del primer
   Directory.Move y antes del segundo; si cambia o caduca,
   deja la carpeta en escrow para revisión. No auto-reintenta.
   Todas las comprobaciones de ACL sobre staging, archivos, escrow
   y destino siguen usando el SID obtenido de esa misma fuente.

El registro es parte de la configuración de prueba creada por una
identidad administrativa de confianza. El proceso copiador bajo un
SID Windows separado no puede leerlo ni modificarlo. No se instala
una cuenta o servicio persistente.

## Pruebas positivas y negativas (Windows nativo)

scripts/test_viewtv_windows_broker_handoff_sandbox.ps1:
**14 comprobaciones correctas**.

- Rechazo de vault sin protección.
- Rechazo de registro ausente: no hay publicación.
- Rechazo de argumento -CopySid de cliente: ya no existe.
- Rechazo de broker_sid distinto al SID del proceso real.
- Rechazo de registro caducado.
- Rechazo de ACE Users añadida al registro.
- Aceptación de registro privado válido (el SID se resuelve sin argumento).
- Rechazo de ACE de lectura del copiador sobre el vídeo.
- Rechazo de ACE Users sobre staging.
- Publicación en dos renames con SHA-256 íntegro.
- Rechazo de descriptor escritor preabierto y éxito tras cierre.
- Rechazo de manifest firmado modificado.

Este test emplea SID sintético para la ACE de copia y la identidad
elevada del operador como broker: **no es una prueba de servicio real**.

scripts/test_viewtv_windows_distinct_sids_sandbox.ps1:
**14 comprobaciones correctas**.

- Crea dos cuentas Windows LOCALES de prueba con SIDs distintos,
  ambas no administrativas, solo durante la ejecución.
- Inscribe sus SIDs reales en una cámara privada con tres ACE.
- Bajo impersonación real del copiador, demuestra denegación de lectura
  Y escritura de .viewtv-copy-identity.json.
- Bajo impersonación real del broker, el lector recupera el SID de
  copia del registro sin argumento.
- Conserva los controles previos de DACL, aislamiento escrow,
  SHA-256 y bloqueo de escritor abierto.
- El finally borra solo cuentas que coinciden en nombre, SID y
  descripción, y carpetas GUID marcadas sin enlaces.

Regresiones ejecutadas:
- test_viewtv_windows_publish_sandbox.ps1: 20 controles correctos.
- test_viewtv_windows_restricted_acl_sandbox.ps1: 29 correctos.
- Backend en Ubuntu/WSL: **545 pruebas aprobadas, 2 advertencias de
  deprecación, exit code 0 (36,90 s)**, sin caché ni bytecode.
- PowerShell Parser de todos los scripts editados: correcto.
- Sin datos de producción tocados.

## Respaldo de hito anterior a cambios

Archivo:
~/viewtv-backups/identidad-broker-sid-20261120-145535.tar.gz

SHA-256:
f8792f3f7b62ac1be338c6bc8adb2d54a2c3250702cc62db9f55b7ce4f1c75de

Verificación tar -tzf: contiene exactamente:
- scripts/viewtv_windows_broker_handoff_sandbox.ps1
- scripts/viewtv_windows_publish_sandbox.ps1
- scripts/test_viewtv_windows_broker_handoff_sandbox.ps1
- scripts/test_viewtv_windows_distinct_sids_sandbox.ps1
- docs/ORGANIZADOR-GATE-ACL-COPIADOR-SANDBOX.md

El lector y este documento se crean nuevos y carecían de versión
anterior que respaldar.

## Límites abiertos — no confundir con producción

- La inscripción es creada por un INICIALIZADOR DE PRUEBAS bajo una
  identidad administrativa. El broker definitivo debe custodiar
  ese registro, controlar el alta de identidades y operar como
  proceso o servicio real con cuenta de bajo privilegio,
  separado del worker y de la administración.
- Esta verificación se hace mediante rutas de archivos. Una cuenta
  privilegiada hostil puede sustituir archivos o intervenir en el
  intervalo entre comprobación y uso. No hay afirmación de cierre
  general de TOCTOU ni contra administrador.
- NO se valida aquí un lease 0013, attempt, propiedad del torrent,
  replay por download_id, diario de operaciones ni transacción
  NTFS+SQLite. No se prueba corte de energía o copia multigiB.
- El límite de pruebas permanece en 32 MiB por archivo y en el
  sandbox GUID. No se habilita worker/main.py ni el start de descarga.
- Sigue sin repararse el desajuste de imagen API/worker en el despliegue
  0012; resolverlo requerirá diagnóstico y respaldo específicos.
- PR #2 debe permanecer draft y sin fusionar.

**Decisión:** frontera del SID más sólida en sandbox, pero aún NO
equivale a un broker independiente autorizado para producción.
