# VIEWTV 0013 — frontera ACL con dos SID de Windows reales (solo sandbox)

Fecha: 20-11-2026. Rama: `viewtv-seguimiento-descargas-0012`.
**No se ha instalado ningún servicio ni se ha modificado producción.**

## Objetivo y método

Prueba nueva: `scripts/test_viewtv_windows_distinct_sids_sandbox.ps1`.
Se ejecuta en Windows PowerShell 5.1, invocada desde el conector, con
código guardado en el árbol de desarrollo **Ubuntu/WSL**.
El parámetro `-AuthorizeEphemeralAccounts` es obligatorio.

La prueba crea exactamente DOS cuentas Windows locales aleatorias
no administrativas, con nombre de uso único `vtcp...` y `vtbr...`,
credenciales aleatorias generadas en memoria y sin registro de contraseñas.
No modifica ni reutiliza usuarios existentes. Obtiene tokens reales mediante
`LogonUserW` de tipo `LOGON32_LOGON_NETWORK` y ejecuta operaciones de archivos
con `WindowsIdentity.Impersonate` para cada SID. Cada identidad se comprueba
contra el SID de la cuenta creada y se rechaza si conserva rol Administradores.
Estas son cuentas Windows distintas, **no el mismo SID con RestrictedCodeSid**.

Toda la actividad de archivos se confina a una carpeta nueva de
`C:\Users\Public\viewtv-win-sandbox-<GUID>` con marcador conocido. No se
usan `C:\VIEWTV\media`, qBittorrent, Jellyfin ni SQLite. Las cuentas se
eliminan por nombre, SID y descripción verificados dentro del `finally`.
La eliminación del sandbox requiere GUID propio, marcador y ausencia de
puntos de reanálisis. Una cuenta ajena nunca se borra.

## Descubrimiento negativo reproducido y corrección

**Primer ensayo: FALLÓ de forma segura.** Con permisos de lectura
explícitos para el SID copiador en la carpeta sellada y en el archivo,
el primer `Directory.Move` hacia un padre privado del broker **no
eliminó esos permisos**. Aunque la DACL del padre `vault` no autorizaba
al copiador, este pudo acceder al archivo mediante ruta conocida
(`Copia pudo acceder al escrow tras move`). No basta con proteger
solo el padre; Windows puede omitir la comprobación de recorrido de
carpetas y conserva la DACL del objeto movido.

**Corrección ensayada:** al sellar se retiran *todas* las ACE de acceso
del **SID real del copiador** tanto de la carpeta staging como de
cada archivo. Los administradores de la prueba y el SID broker sí
conservan permisos. Solo entonces se realiza el primer movimiento a
vault. Tras el cambio, se comprueba expresamente que la copia no
puede leer el escrow ni escribir el destino, mientras el broker
puede realizar ambos movimientos. No se considera suficiente un
preflight que compruebe solo el RestrictedCodeSid genérico.

## Resultados reales

La ejecución corregida terminó con código de salida 0 y siete resultados:

| Prueba | Resultado |
|---|---|
| Dos SID independientes, sin rol Administrador | `verificado` |
| Copia no lee/escribe vault ni crea destino | `copia_denegada` |
| Copia no escribe tras sellado | `escritura_denegada` |
| Primer movimiento ejecutado por broker real; copia no lee escrow | `correcto` |
| Segundo movimiento por broker; SHA-256 íntegro y copia sin escritura | `correcto` |
| Descriptor abierto por copia antes del sellado | `bloquea_move` |
| Cierre voluntario del descriptor y movimiento posterior | `move_correcto` |

Tras ambas ejecuciones (fallida y corregida) se comprobó:

- Cuentas temporales `vtcp...` / `vtbr...` restantes: **0**.
- Carpetas `viewtv-win-sandbox-*` restantes en Public: **0**.
- Directorios de claves temporales `viewtv-test-key-*`: **0**.

No se modificaron servicios ni contraseñas preexistentes.

### Ejecución explícita

En PowerShell 5.1 elevado:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-24.04\home\viewtv\projects\viewtv-broker-0013-20261119\scripts\test_viewtv_windows_distinct_sids_sandbox.ps1" -AuthorizeEphemeralAccounts
```

La ejecución sin `-AuthorizeEphemeralAccounts` es un rechazo antes de crear
usuarios. **No ejecutarlo contra otro directorio**; no recibe rutas externas.

## Limitaciones importantes

- Aunque los SID son reales y los accesos NTFS se prueban por
  impersonación, el proceso anfitrión de pruebas sigue siendo un
  PowerShell elevado. **Esto no equivale a ejecutar un servicio broker
  permanente bajo un SID de bajo privilegio.**
- No hay todavía credencial del broker instalada, ciclo de vida de
  servicio, comprobación independiente de lease/attempt/qBittorrent,
  journal durable con recuperación ni garantía NTFS+SQLite.
- Los SIDs de prueba se destruyen al final: no son cuentas definitivas.
- La prueba usa archivos pequeños ficticios; no avala I/O de varios GiB
  ni fallos físicos o corte de energía.
- El código de publicación `-BrokerHandoff` preexistente es optativo
  y aún no debe considerarse seguro bajo una identidad real de copia
  que conserve ACE de lectura. El futuro broker deberá exigir como
  invariantes: **ninguna ACE para el SID copiador en el staging sellado,
  archivo por archivo, ni en los objetos dentro del escrow**.

## Respaldos verificados

Antes de actualizar los documentos existentes:

`~/viewtv-backups/sid-separados-sandbox-pre-20261120-140749.tar.gz`

SHA-256: `56d9408c9cf0b00d0bab3df5cbac4bf22f265c86c4ebc5f72068dc39e4dbac0b`

`tar -tzf` verificó solo:

- `docs/ENTORNO-CONECTOR.md`
- `docs/ORGANIZADOR-ENTREGA-PRIVADA-NTFS-SANDBOX.md`

La primera versión de la prueba fallida quedó respaldada antes de
corregirla en:

`~/viewtv-backups/acl-dos-sids-prueba-fallida-20261120-141257.tar.gz`

SHA-256: `b2b105ab48ba58ff3e9819bf897cbb2aa157f61db52e5942c73fd91fb628463c`

`tar -tzf` verificó
`scripts/test_viewtv_windows_distinct_sids_sandbox.ps1`.

El documento presente es nuevo y no tiene versión anterior que respaldar.

## Integración posterior del gate (20-11-2026)

El publicador sandbox con `-BrokerHandoff` comprueba desde ahora que
se ha especificado el SID de copia y que ni staging, archivos, escrow
ni destino conservan ninguna ACE para él. Las pruebas de dos cuentas
reales se ampliaron con el mismo guard: se rechaza un staging escribible
y también una ACE de solo lectura inyectada, y se aceptan DACL selladas
en staging, escrow y destino. **12 resultados correctos** en la versión
ampliada. La ejecución del publicador firmado bajo un servicio Windows
no administrativo sigue pendiente.

Véase [ORGANIZADOR-GATE-ACL-COPIADOR-SANDBOX.md](ORGANIZADOR-GATE-ACL-COPIADOR-SANDBOX.md).

## Decisión

**Avance comprobado de separación SID en sandbox.** No es un despliegue
de VIEWTV 0013. Antes de dar por cerrada la frontera de confianza,
probar servicio broker no administrativo real, control exclusivo del
diario y clave, revalidación de lease/intento/torrent antes de publicar,
replay por descarga, interrupciones durables y tamaños reales. El PR #2
seguirá en borrador; no fusionar ni tocar la biblioteca real.
