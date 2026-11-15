# Nota técnica: Normalización y exploración de transacciones multifuente

**Autor:** Jonathan Alberto · **Curso:** AI for Developers Jr. 4 · **IA de apoyo:** Claude (Anthropic)

## 1. Decisiones de diseño

- **Modelo común de 6 campos** (`id`, `amount`, `currency`, `timestamp`, `status`, `source`), con el monto como `Decimal` para que las sumas por moneda sean exactas y la fecha en ISO-8601 UTC.
- **Un módulo por responsabilidad:** normalización, validación, métricas, filtros e interfaz están separados. La interfaz solo muestra y pide datos, sin lógica de negocio.
- **Reglas en `reglas.json`,** no en el código: mapeo de estados, monedas, formatos de fecha y campos de cada fuente. Cambiar una regla o añadir una fuente no requiere editar el código, y una prueba lo comprueba.
- **Se detectan todos los problemas de un registro,** no solo el primero, y cada transacción inválida conserva su original y sus motivos.

## 2. Uso de la IA: qué hizo ella y qué decidí yo

**La IA** estructuró el código, escribió la lógica de lectura de montos y fechas, la interfaz CLI, los datos de prueba y las 42 pruebas automáticas.

**Yo decidí tres reglas,** que la consigna reserva al estudiante:

1. Las transacciones inválidas se **separan** en una lista aparte, con su motivo, visible en la interfaz.
2. El monto entero de la segunda fuente son **centavos** (`10050` equivale a `100.50`).
3. Un estado desconocido o ausente se mapea a **`FAILED`**.

El resto de las reglas (monedas soportadas, formatos de fecha, monto mayor que 0, ids duplicados, etc.) fueron **propuestas de la IA**. Están identificadas con ese origen en `reglas.json` y en el README. La tercera decisión implica que un registro sin estado cuenta como válido, así que para no perder esa información se registran **avisos** visibles en la interfaz.

## 3. Ajustes realizados sobre el código propuesto por la IA

Al revisar la salida real de la interfaz, y no solo las pruebas, aparecieron dos defectos en el código propuesto:

- **Motivos de rechazo mal agrupados.** El mismo tipo de error salía en categorías distintas (`monto no numérico` y `monto no numérico (valor booleano)`), porque el agrupamiento cortaba el texto solo en los dos puntos. Se corrigió cortando también en `(` y `;`, y se añadió una prueba que verifica los conteos por categoría.
- **Monto sin formato monetario.** El detalle de una transacción mostraba `40.0` en lugar de `40.00`. Se corrigió y se añadió una prueba.

## 4. Validación

Los resultados esperados de cada archivo de datos se calcularon **a mano antes de ejecutar** y se compararon con lo obtenido (válidos, inválidos, conteo por estado y totales por moneda). Los archivos de prueba incluyen datos válidos, 17 tipos de inconsistencia y errores de archivo (JSON malformado, lista vacía, archivo inexistente).

## 5. Limitaciones conocidas

No se convierten monedas entre sí; las fechas sin zona horaria se asumen UTC; y `1,234` se interpreta como miles, no como decimal.
