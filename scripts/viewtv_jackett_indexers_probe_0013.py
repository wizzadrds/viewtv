"""Consulta solo lectura de indexadores Jackett, SIN búsquedas ni secretos."""
import re

from app.jackett import JackettClient

try:
    client = JackettClient()
    indexers = client.get_indexers()
except Exception:  # noqa: BLE001 -- nunca mostrar secretos de consulta
    print("JACKETT_INDEXERS_ERROR=NO_SE_PUDO_CONSULTAR")
    raise SystemExit(1)

print("JACKETT_CATALOGO_INDICES_TOTAL=" + str(len(indexers)))
print("JACKETT_CONFIGURADOS=" + str(sum(i.configured is True for i in indexers)))
print("JACKETT_SIN_CONFIGURAR=" + str(sum(i.configured is False for i in indexers)))
print("JACKETT_ESTADO_DESCONOCIDO=" + str(sum(i.configured is None for i in indexers)))
configured = [i for i in indexers if i.configured is True]
for indexer in configured[:30]:
    # Nombre amigable no contiene claves ni rutas; nunca mostrar valores de URL.
    name = re.sub(r"[^a-zA-Z0-9_.-]", "_", indexer.id)[:65]
    print("INDEXADOR_CONFIGURADO=" + name)
print("JACKETT_METADATOS_SIN_BUSQUEDA=OK")
