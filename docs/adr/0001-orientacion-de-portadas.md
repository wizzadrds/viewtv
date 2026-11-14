# ADR 0001: orientación de las portadas

- **Estado:** pendiente de decisión del propietario.
- **Fecha:** 2026-11-14.
- **Ámbito:** presentación de las carátulas en las filas del catálogo y en la ficha de detalle.
- **Decisión aplicada:** ninguna.

## Contexto

La especificación de VIEWTV contempla pósteres verticales con proporción 2:3 en las filas del catálogo y fondos panorámicos 16:9 en la ficha de detalle. Sin embargo, el trabajo de interfaz mencionado en el documento de contexto ha utilizado portadas horizontales sin que exista una decisión registrada.

Es necesario elegir una orientación antes de consolidar el diseño. Este documento registra las alternativas; no autoriza a cambiar la interfaz ni los recursos existentes.

## Opciones

### A. Póster vertical 2:3 en las filas

Todas las filas del catálogo muestran pósteres verticales 2:3. La ficha de detalle puede conservar su composición actual hasta que se defina expresamente en otra decisión.

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

## Recomendación

La recomendación inicial es **C**, porque coincide con la especificación recogida en `docs/CONTEXTO.md` y asigna un uso claro a cada formato.

Esta recomendación no constituye una decisión ni debe implementarse sin confirmación expresa.

## Decisión

**Pendiente.** El propietario debe elegir A, B o C.

Hasta entonces:
- no cambiar la orientación de las portadas;
- no modificar componentes, estilos ni datos de imágenes;
- no asumir que la recomendación equivale a una aprobación.

## Consecuencias

Se actualizará este ADR con la opción elegida y su justificación. La implementación se realizará únicamente cuando el propietario la autorice como siguiente paso.
