# VIEWTV — Organizador de archivos: fase 1, planificación sin escritura

> **Avance posterior (0013, desarrollo, NO desplegado):** se ha implementado una cola durable de organización con leases y reintentos, todavía sin ejecutor ni escritura. Ver [ORGANIZADOR-COLA-0013.md](ORGANIZADOR-COLA-0013.md). Producción sigue en `0012`.

Fecha: 19/11/2026. Código de desarrollo; NO desplegado en producción.

## Estado

El módulo worker/organization_planner.py es una función de PLANIFICACIÓN. Devuelve una lista inmutable de archivos de origen y destino; NO copia, mueve, crea directorios, borra ni consulta qBittorrent. No está conectado al worker real.

Condiciones de entrada: la descarga debe estar completada, con progreso 100 % y verificación confirmada; debe corresponder a la solicitud propietaria. El resultado de verificación de archivos y la identidad exacta del torrent deben volver a comprobarse al ejecutar una futura operación de escritura.

## Reglas de planificación

- Origen previsto: /media/descargas_temporales, ya comprobado por worker/file_validator.py y worker/completed_files.py.
- Bibliotecas previstas: /media/Peliculas y /media/Series, actualmente montadas de solo lectura en el worker de producción.
- Película: Peliculas/Titulo (Año)/Titulo (Año).mkv (sin Año cuando la solicitud no lo tiene).
- Serie de episodio único: Series/Nombre/Temporada 01/Nombre - S01E02.mkv.
- Subtítulos con el mismo nombre raíz que el vídeo, y en la misma carpeta, mantienen la etiqueta de idioma, por ejemplo .es.srt.
- En esta primera fase se admite UN único archivo de vídeo por descarga y una lista corta de subtítulos seguros. Las descargas con varios episodios, extras no admitidos, múltiples vídeos o nombres ambiguos requieren revisión manual.
- Formatos iniciales de vídeo: MKV, MP4, M4V y AVI. Subtítulos: SRT, ASS y VTT.
- Titulos peligrosos para Windows, rutas fuera de la raíz, enlaces simbólicos, archivos vacíos, duplicados y colisiones sin distinguir mayúsculas son bloqueados.
- Se rechaza añadir una película a la carpeta de otra ya existente. En series se pueden usar carpetas seguras de temporadas ya existentes, pero NO sobrescribir episodios.
- Estas decisiones priorizan seguridad sobre cobertura. La nomenclatura se revisará en pruebas de Jellyfin.

## Pruebas y límites

- backend/tests/test_organization_planner.py: 34 pruebas nuevas, exclusivamente con rutas temporales de pytest.
- Suite total backend: **347 passed, 2 warnings**; Ruff limpio.
- No se ha accedido a archivos de películas, series o torrents reales.
- La planificación NO es prueba suficiente para escribir: existe riesgo de cambios de archivos entre validación y copia (TOCTOU).
- No hay migración Alembic nueva ni modificación de compose. La bandera de inicio automático sigue desactivada en producción.

## Fase 2 obligatoria ANTES de habilitar organización real

1. Establecer una cola durable de organización con lease, estados, reintentos controlados y recuperación tras reinicios; modelo/migración adicional, pruebas multiworker.
2. Revalidar hash, etiqueta de VIEWTV, ruta qBittorrent, estado verificado en DB, tamaño, estructura y contenido de todos los archivos justo antes de copiarlos.
3. Habilitar escritura SOLO en carpetas de destino estrictamente delimitadas. Mantener origen y volumen de datos protegidos; no añadir escritura indiscriminada a /media.
4. Copia temporal de cada archivo con comprobaciones de integridad y espacio libre, permisos y políticas de enlaces, seguida de publicación atómica cuando sea posible.
5. Política explícita para reintentos tras caída: no duplicar archivos ni borrar el origen mientras qBittorrent pueda compartirlos; resolver idempotencia y colisiones antes de actuar.
6. Manejar multi-episodios, subtítulos, extras, títulos duplicados y temporadas ya existentes; la ambigüedad va a revisión manual.
7. Probar solo con contenido autorizado y medios ficticios en directorios temporales, luego en una biblioteca de pruebas, antes de Jellyfin real.
8. Comprobar escaneo Jellyfin y reproducción real desde VIEWTV con revisión visual del usuario.

**Estado actual: planificador validado, ejecutor NO implementado. No habilitar ni desplegar como organizador operativo.**
