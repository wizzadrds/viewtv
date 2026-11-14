# ADR 0001: orientación de las portadas

- **Estado:** aceptado.
- **Fecha de decisión:** 2026-11-14.
- **Ámbito:** presentación de las carátulas en las filas del catálogo.
- **Decisión:** opción A, póster vertical 2:3 en las filas.

## Contexto

La especificación de VIEWTV contempla pósteres verticales con proporción 2:3 en las filas del catálogo. Durante el trabajo de interfaz se han probado también portadas horizontales, por lo que era necesario registrar una decisión explícita antes de consolidar el diseño.

## Opciones consideradas

### A. Póster vertical 2:3 en las filas

Todas las filas del catálogo muestran pósteres verticales 2:3.

**Ventajas**
- Sigue la especificación original para las filas.
- Mantiene una presentación reconocible como catálogo de cine.
- Aprovecha las carátulas verticales habituales de películas.

**Inconvenientes**
- Muestra menos elementos en horizontal a igualdad de anchura disponible.
- Puede requerir adaptar el trabajo de interfaz horizontal ya realizado.

### B. Portadas horizontales en las filas

Las filas del catálogo utilizan imágenes apaisadas.

**Ventajas**
- Mantiene el enfoque horizontal que se ha estado probando en la interfaz.
- Permite mostrar imágenes panorámicas y aprovechar mejor el ancho de cada tarjeta.

**Inconvenientes**
- Se aparta de la especificación original de pósteres 2:3 en las filas.
- Puede requerir recortar o adaptar las carátulas verticales.

### C. Diseño mixto: 2:3 en filas y 16:9 en detalle

Las filas del catálogo muestran pósteres verticales 2:3. La ficha de detalle utiliza un backdrop panorámico 16:9.

**Ventajas**
- Respeta la especificación original completa.
- Diferencia visualmente la navegación por catálogo de la presentación de una película.
- Permite utilizar cada tipo de imagen en el contexto para el que está pensado.

**Inconvenientes**
- Requiere disponer de dos imágenes o variantes cuando estén disponibles.
- La interfaz debe contemplar una alternativa cuando falte el póster o el backdrop.

## Decisión

Se elige **A: póster vertical 2:3 en todas las filas del catálogo**.

La decisión ha sido confirmada expresamente por el propietario. La opción C no se adopta: este ADR no establece el uso obligatorio de un backdrop 16:9 en la ficha de detalle. El diseño del detalle queda fuera del alcance de esta decisión y no debe inferirse de ella.

## Consecuencias

- Las tarjetas de películas de las filas del catálogo utilizarán proporción 2:3.
- La interfaz existente que use portadas horizontales en esas filas deberá adaptarse cuando se autorice el trabajo de implementación correspondiente.
- No se realizan cambios de interfaz, estilos ni recursos de imágenes como parte de la aceptación de este ADR.
- Las imágenes de detalle no quedan sujetas a una proporción específica por esta decisión.

## Estado de implementación

**Decisión aceptada; implementación pendiente.** Registrar esta decisión no autoriza a adelantar otras fases ni a modificar ahora componentes de la interfaz.
