# VIEWTV 0013 — entrega privada de staging NTFS (prototipo SOLO SANDBOX)

Fecha: 20-11-2026. Rama: viewtv-seguimiento-descargas-0012.
**No es un cierre de TOCTOU apto para producción ni un broker con SID independiente.**
No conectar a worker/main.py, qBittorrent real ni C:\VIEWTV\media.

## Problema y resultado negativo verificado

El preflight anterior observa un instante sin descriptores de escritura, pero
libera sus handles antes de Directory.Move. Se intentó una barrera más fuerte:
abrir carpeta y archivos con GENERIC_READ + FILE_SHARE_DELETE, mantenerlos
abiertos para leer SHA-256 desde los mismos handles y ejecutar Directory.Move
sin soltarlos. **Falló** en el NTFS de este equipo con "Acceso denegado" al
mover una carpeta que tenía handles de lectura vivos, incluso usando
FileShare.Delete. Otro ensayo PowerShell con un único FileStream abierto
FileAccess.Read/FileShare.Delete produjo el mismo rechazo.

**No se integró** ese experimento en el publicador. El código de prueba
rechazado quedó preservado, sin borrarlo, en:
- ~/viewtv-backups/prototipo-held-quiescencia-rechazado-20261120.ps1
- ~/viewtv-backups/test-held-quiescencia-rechazado-20261120.ps1

Archivo de evidencia de ambos:
~/viewtv-backups/prototipo-held-ntfs-no-valido-20261120-133912.tar.gz
SHA-256: 8a61c9c2b6db65e711ef8d3ccc7b4901fe76f1d21c0e41422ac603d03961f06d.
Se verificó el contenido exacto mediante tar -tzf.

## Alternativa ensayada, optativa y conservadora

Nuevo helper: scripts/viewtv_windows_broker_handoff_sandbox.ps1.
Nueva batería: scripts/test_viewtv_windows_broker_handoff_sandbox.ps1.
El publicador de pruebas acepta ahora **-BrokerHandoff**. El modo histórico
sigue siendo el predeterminado, para no cambiar las pruebas anteriores.

En un sandbox GUID recién creado en C:\Users\Public y con marcador obligatorio:

1. El proceso de copia debe cerrar sus handles por sí mismo. Una DACL
   protegida y propietario Administradores dejan staging y archivos solo
   en lectura para el RestrictedCodeSid. No se fuerza ni mata ningún proceso.
2. Un directorio '.viewtv-broker-handoff' debe existir previamente bajo
   el mismo sandbox, con DACL protegida, propietario Administradores y
   solo las tres identidades de ensayo permitidas (cuenta completa, SYSTEM,
   Administradores); la identidad de copia restringida no tiene acceso.
   No se crean ni modifican ACL fuera del GUID.
3. El publicador valida HMAC, hashes, identidad NTFS y ausencia observable
   de handles. Rechaza destino existente y escrow previo.
4. Un primer Directory.Move traslada la carpeta completa sellada a
   '.viewtv-broker-handoff/.viewtv-handoff-N'. **Esta no es la publicación
   final:** se transfiere a un padre privado del broker. Ante error o
   ambigüedad se requiere revisión, sin borrado ni reintento automático.
5. Dentro del directorio privado, se revalidan DACL, propietario, números
   de archivo/volumen NTFS, nombres, tamaños, SHA-256 y caducidad de la
   intención. Si algo cambia, se conserva el escrow para revisión.
6. Un segundo Directory.Move publica el grupo completo en carpeta nueva;
   la verificación firmada postpublicación existente vuelve a comprobar
   archivos e identidad. No hay sobrescritura.

**Propiedad esencial y límite:** en el ensayo, un descriptor de escritura
abierto antes de sellar evita el primer Directory.Move; tras cerrarlo,
la entrega se completa. Una identidad realmente separada que no pueda
leer ni atravesar el padre privado tampoco podrá abrir nuevos handles
después del primer movimiento. Sin esa identidad separada la cuenta
Windows original conserva autoridad de modificar ambos lados: por ello,
**el problema de TOCTOU sigue abierto frente a esa cuenta**.

Tampoco hay transacción NTFS/SQLite. Un fallo entre primer y segundo Move
dejaría escrow para conciliación, pero no se ha probado aquí una caída
física o abrupta. No se protege aún contra un administrador hostil,
hardlinks/reparse creados por una cuenta privilegiada ni otro servicio
que ignore las ACL. No sirve para varios GiB (límite 32 MiB por archivo),
no autentica lease/attempt/torrent, ni controla replay global por descarga.

## Resultados observados (PowerShell nativo Windows)

Nuevo test: seis resultados correctos:
- vault_sin_proteger = rechazado.
- copia_no_escribe_escrow = denied, con token restringido real.
- handoff_y_publicacion_ntfs = correcto, con SHA-256 final exacto.
- escritor_preabierto = rechazado; no se movió staging a escrow.
- cierre_y_reintento_de_prueba = correcto (únicamente después del cierre
  voluntario del descriptor; no auto-reintento del publicador).
- sha_modificado_antes_de_entrega = rechazado sin movimiento.

Regresiones del publicador y reconciliación: **20 escenarios correctos**.
Regresión ACL/quiescencia: **29 resultados correctos**, incluido error Win32
32 y rechazo de handles de carpeta, sin alterar sus pruebas.
**Backend: 545 passed, 2 warnings conocidos, exit code 0 (39.24 s)**
con `-p no:cacheprovider` y `PYTHONDONTWRITEBYTECODE=1`.
`git diff --check` sin errores. La prueba nueva concluyó con código 0.
Las baterías utilizan sandbox GUID y claves efímeras exclusivamente; al
terminar se borran solo los recursos que los tests crearon y marcaron.
No se usó la SQLite real ni un torrent.

Ejecutar de forma explícita desde PowerShell de Windows (NO producción):

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_broker_handoff_sandbox.ps1"

## Respaldo previo obligatorio y auditado

ANTES de editar el publicador y el documento existente:
~/viewtv-backups/quiescencia-durable-pre-20261120-132331.tar.gz
SHA-256: e723235c01b9d8e27c68c8c86116ab3275adab5cafaeec35b1b04b89990aa8e9

tar -tzf mostró exactamente:
- scripts/viewtv_windows_publish_sandbox.ps1
- docs/ORGANIZADOR-QUIESCENCIA-NTFS-SANDBOX.md

Los demás archivos de este hito fueron creados desde cero.
No se respaldó la base de producción porque no se escribió en ella.

## Próximos bloqueos antes de cerrar fase 1

- Crear/usar dos cuentas Windows con SID verdaderamente distinto y
  privilegios mínimos, con pruebas ejecutadas bajo la identidad de copia.
  El conector actual bloquea comandos administrativos net/sc/runas; no
  sortear esa restricción ni simular cuentas.
- Decidir la custodia del secreto y quién valida desde una autoridad ajena
  al worker, ligando lease 0013, attempt, hash real de torrent, manifiesto
  y replay por download_id.
- Mantener el control exclusivo de la cámara privada durante todo el
  proceso y registrar transiciones durables entre escrows, publicación y
  confirmación SQLite. Probar también fallos abruptos y varios GiB.
- Reparar antes la discrepancia entre API y worker de producción 0012,
  detectada durante la fase 0. No migrar ni desplegar 0013 ahora.

**Decisión:** hito de avance en sandbox, sin declaración de TOCTOU cerrado,
sin cambios a producción. PR #2 sigue draft. Bandera
VIEWTV_ENABLE_DOWNLOAD_START=false.
