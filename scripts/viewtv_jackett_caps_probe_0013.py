"""Leer SOLO capacidades Torznab de los indexadores configurados.

No consulta resultados ni títulos, y jamás emite API keys ni URLs.
"""
import re
import xml.etree.ElementTree as ET

import httpx
from app.jackett import JackettClient

client = JackettClient()
indexers = [i for i in client.get_indexers() if i.configured is True]
print("CONFIGURADOS="+str(len(indexers)))
for item in indexers[:12]:
    safe = re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", item.id)
    if safe is None:
        print("INDEXADOR_ID_NO_VERIFICABLE")
        continue
    try:
        with httpx.Client(base_url=client._base_url, timeout=8, follow_redirects=False) as http:
            response = http.get(
                "/api/v2.0/indexers/" + item.id + "/results/torznab/api",
                params={"apikey": client._api_key, "t": "caps"},
            )
        if response.status_code != 200:
            print("INDICE="+item.id+" CAPS_ESTADO=HTTP_"+str(response.status_code))
            continue
        root = ET.fromstring(response.content)
        modes = set()
        categories = set()
        for e in root.iter():
            tag = e.tag.rsplit("}",1)[-1].lower()
            if tag in {"search", "tv-search", "movie-search"}:
                modes.add(tag)
            if tag == "category":
                code = e.attrib.get("id","")
                if code.isdecimal() and len(code)<6:
                    categories.add(int(code)//1000*1000)
        print("INDICE="+item.id+" CAPS_OK=SI MODOS="+",".join(sorted(modes))
              +" FAMILIAS="+",".join(str(n) for n in sorted(categories)))
    except (httpx.HTTPError, ET.ParseError, ValueError):
        print("INDICE="+item.id+" CAPS_ESTADO=NO_VERIFICADO")
print("JACKETT_CAPS_SOLO_METADATOS=SI")
