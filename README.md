# 💳 Normalización y Exploración de Transacciones Multifuente

Sistema en Python que lee transacciones de varias fuentes con estructuras distintas, las **normaliza a un formato común**, **valida** cada registro y permite **explorarlas con una interfaz interactiva** (menú, filtros, métricas y detalle).

> **Actividad:** Normalización y Exploración de Transacciones Multifuente
> **Curso:** AI for Developers Jr. 4 · KODIGO Academy
> **Autor:** Jonathan Alberto
> **IA de apoyo:** Claude (Anthropic)

La nota técnica con las decisiones de diseño y el uso de IA está en [`NOTA_TECNICA.md`](NOTA_TECNICA.md).

---

## 📋 Contenido

1. [Ejecución](#-ejecución)
2. [Estructura del proyecto](#-estructura-del-proyecto)
3. [Esquema normalizado](#-esquema-normalizado)
4. [Reglas de normalización y validación](#-reglas-de-normalización-y-validación)
5. [Métricas](#-métricas)
6. [Interfaz interactiva](#-interfaz-interactiva)
7. [Datos de prueba y resultados](#-datos-de-prueba-y-resultados)
8. [Limitaciones conocidas](#-limitaciones-conocidas)

---

## 🚀 Ejecución

**Requisitos:** Python 3.8 o superior (desarrollado y probado con Python 3.12). No usa librerías externas.

```bash
# Elegir un archivo de la carpeta datos/ desde el menú
python main.py

# O indicar el archivo directamente
python main.py datos/transacciones_validas.json

# Ejecutar las pruebas automáticas (42)
python -m unittest discover -s tests -v
```

---

## 📁 Estructura del proyecto

```
transacciones_multifuente/
├── main.py               # Punto de entrada
├── reglas.json           # Reglas: estados, monedas, formatos de fecha, fuentes y decisiones
├── config.py             # Carga y comprueba reglas.json
├── modelos.py            # Modelo de datos (esquema normalizado)
├── normalizador.py       # Normalización: montos, moneda, fecha, estado, detección de fuente
├── validador.py          # Validación: criterios de validez
├── procesador.py         # Lectura del JSON y orquestación
├── metricas.py           # Cálculo de métricas
├── filtros.py            # Filtros de exploración
├── interfaz.py           # CLI interactiva
├── datos/                # Archivos de prueba (válidos e inconsistentes)
├── tests/                # Pruebas automáticas
├── README.md
└── NOTA_TECNICA.md
```

Cada módulo tiene **una sola responsabilidad**, como pide la consigna: normalización, validación, métricas e interfaz están separadas. La interfaz no contiene lógica de negocio.

---

## 🧱 Esquema normalizado

Todas las transacciones válidas terminan con estos 6 campos:

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | texto | Identificador de la transacción |
| `amount` | decimal (2 decimales) | Monto en unidades de la moneda |
| `currency` | texto | Código de moneda en mayúsculas (`USD`, `EUR`, `GBP`) |
| `timestamp` | texto ISO-8601 | Fecha y hora en UTC, por ejemplo `2025-03-10T14:22:00Z` |
| `status` | texto | `SUCCESS`, `FAILED` o `PENDING` |
| `source` | texto | Fuente de origen (`fuente_A`, `fuente_B`, `fuente_C`) |

Internamente el monto es `Decimal` y no `float`, para que las sumas por moneda sean exactas.

**Las tres fuentes del enunciado y cómo se unifican:**

| Fuente | Registro original | Resultado normalizado |
|---|---|---|
| `fuente_A` | `{"id":"tx_001","amount":"100.50","currency":"USD","timestamp":"2025-03-10 14:22:00","status":"completed"}` | 100.50 USD · `2025-03-10T14:22:00Z` · SUCCESS |
| `fuente_B` | `{"transaction_id":204,"total":10050,"currency_code":"usd","created_at":"10/03/2025 14:22","state":"OK"}` | 100.50 USD · `2025-03-10T14:22:00Z` · SUCCESS |
| `fuente_C` | `{"ref":"A-77","amount":"€99,99","date":"2025-03-10T14:22:00Z","result":"success"}` | 99.99 EUR · `2025-03-10T14:22:00Z` · SUCCESS |

---

## ⚖️ Reglas de normalización y validación

Las reglas viven en [`reglas.json`](reglas.json) y la consigna indica que la IA **no debe decidir** el esquema, las reglas de normalización ni los criterios de validez. Por eso cada regla indica su origen:

| # | Regla | Origen |
|---|---|---|
| 1 | Las transacciones inválidas o incompletas se **separan** en una lista aparte, con su motivo, visible en la interfaz | **Decisión mía** |
| 2 | El monto entero de `fuente_B` son **centavos** (`10050` equivale a `100.50`) | **Decisión mía** |
| 3 | Un estado desconocido o ausente se mapea a **`FAILED`** y se registra un aviso | **Decisión mía** |
| 4 | Esquema de 6 campos del enunciado; `amount` con 2 decimales y `timestamp` ISO-8601 en UTC | Propuesta de la IA (basada en el enunciado) |
| 5 | La fuente se detecta por su clave identificadora (`id`, `transaction_id`, `ref`); ninguna o varias es inválida | Propuesta de la IA |
| 6 | Monedas soportadas: USD, EUR y GBP; símbolos `$`, `€`, `£` | Propuesta de la IA |
| 7 | En `fuente_C` la moneda sale del símbolo del monto; sin símbolo es inválida; si símbolo y código se contradicen, es inválida | Propuesta de la IA |
| 8 | El monto debe ser mayor que 0 | Propuesta de la IA |
| 9 | Montos con más de 2 decimales son inválidos (no se redondea en silencio) | Propuesta de la IA |
| 10 | Formatos numéricos: `99,99`, `1.234,56` y `1,234.56`; un solo punto es decimal; `1,234` se lee como miles | Propuesta de la IA |
| 11 | Montos enteros en `fuente_A` y `fuente_C`, textos y decimales son unidades | Propuesta de la IA |
| 12 | Fechas con barras se leen día/mes/año; sin zona horaria se asume UTC; solo fecha es 00:00:00 | Propuesta de la IA |
| 13 | La fecha es obligatoria; una fecha numérica (epoch) no se soporta | Propuesta de la IA |
| 14 | Mapeo de estados según la lista `mapeo_estados` de `reglas.json` | Propuesta de la IA |
| 15 | Un id repetido dentro de la misma fuente: el segundo registro es inválido | Propuesta de la IA |
| 16 | Total por moneda de todas las válidas, más el monto confirmado (solo SUCCESS) | Propuesta de la IA |

Las reglas se pueden cambiar **editando `reglas.json` sin tocar el código**. Por ejemplo, agregar una moneda, un alias de estado, un formato de fecha o una fuente nueva. Una prueba automática comprueba que cambiar `monto_entero_en` o `estado_desconocido` cambia el comportamiento.

**Qué pasa con las transacciones inválidas:** se separan en una lista aparte, conservando el registro original y **todos** los motivos detectados (no solo el primero). La interfaz permite verlas.

---

## 📊 Métricas

Según la consigna, el sistema calcula:

- Total de registros procesados.
- Válidos frente a inválidos (con porcentaje).
- Conteo por estado (`SUCCESS`, `FAILED`, `PENDING`).
- Totales por moneda, con la cantidad, el total de todas las válidas y el monto confirmado (solo `SUCCESS`).

Además informa el conteo por fuente y los motivos de rechazo agrupados por tipo. No se convierten monedas entre sí: los totales se muestran por separado.

---

## 🖥️ Interfaz interactiva

CLI con menú, que no se limita a imprimir un resultado:

```
  1. Ver métricas
  2. Listar transacciones (aplica los filtros activos)
  3. Filtrar transacciones
  4. Ver transacciones inválidas (con su motivo)
  5. Ver avisos de normalización
  6. Buscar una transacción por ID
  7. Ver las reglas aplicadas
  8. Exportar resultados a JSON
  9. Cargar otro archivo
  0. Salir
```

- **Filtros combinables:** estado, moneda, fuente, monto mínimo y máximo, fecha desde y hasta.
- **Listado paginado** de 10 en 10, con la suma de lo mostrado por moneda.
- **Detalle por ID:** muestra la transacción normalizada, el registro original y los avisos.
- **Entradas inválidas** (opción desconocida, monto no numérico, fecha mal escrita) no rompen el programa: muestran un mensaje y siguen.
- **Archivo con errores** (inexistente, JSON malformado, no es una lista): muestra el motivo y conserva los datos ya cargados.

---

## 🧪 Datos de prueba y resultados

Los resultados esperados se calcularon **a mano**, leyendo cada archivo y aplicando las reglas, **antes** de ejecutar el programa. Después se compararon con lo obtenido (las 42 pruebas automáticas verifican estos números).

### `ejemplo_enunciado.json` (los 3 ejemplos del enunciado)

| Métrica | Esperado | Obtenido |
|---|---|---|
| Válidas / inválidas | 3 / 0 | 3 / 0 |
| Los 3 registros normalizados | Mismo instante `2025-03-10T14:22:00Z` y estado `SUCCESS` | Coincide |

### `transacciones_validas.json` (12 registros bien formados)

| Métrica | Esperado | Obtenido |
|---|---|---|
| Válidas / inválidas | 12 / 0 | 12 / 0 |
| SUCCESS / FAILED / PENDING | 6 / 3 / 3 | 6 / 3 / 3 |
| USD (cantidad, total, confirmado) | 6, 7,885.56, 1,401.00 | 6, 7,885.56, 1,401.00 |
| EUR (cantidad, total, confirmado) | 3, 201.23, 99.99 | 3, 201.23, 99.99 |
| GBP (cantidad, total, confirmado) | 3, 84.98, 39.98 | 3, 84.98, 39.98 |

### `transacciones_con_errores.json` (24 registros: 7 válidos y 17 inválidos)

| Métrica | Esperado | Obtenido |
|---|---|---|
| Válidas / inválidas | 7 / 17 | 7 / 17 |
| SUCCESS / FAILED / PENDING | 5 / 2 / 0 | 5 / 2 / 0 |
| USD (cantidad, total, confirmado) | 5, 2,270.00, 2,230.00 | 5, 2,270.00, 2,230.00 |
| EUR (cantidad, total, confirmado) | 2, 1,294.56, 1,234.56 | 2, 1,294.56, 1,234.56 |
| Avisos (estado desconocido o ausente → FAILED) | 2 | 2 |

Los 17 registros inválidos y el motivo que debe detectarse:

| Registro | Problema | Motivo detectado |
|---|---|---|
| #2 | Monto `"abc"` | monto no numérico |
| #3 | Falta `amount` | falta campo obligatorio |
| #4 | Moneda `XYZ` | moneda no soportada |
| #5 | Monto `-20.00` | monto no positivo |
| #6 | Monto `0` | monto no positivo |
| #7 | Fecha `31/02/2025` | fecha no reconocida |
| #10 | Id `e_001` repetido | id duplicado |
| #12 | Monto `true` | monto no numérico (booleano) |
| #13 | Fecha numérica (epoch) | fecha con tipo no soportado |
| #14 | Monto `"12.345"` | más de 2 decimales |
| #15 | `transaction_id` vacío | falta campo obligatorio |
| #16 | Fuente C sin símbolo de moneda | moneda no determinable |
| #18 | Fecha `"not a date"` | fecha no reconocida |
| #19 | Sin clave identificadora | fuente no reconocida |
| #20 | Un texto en lugar de un objeto | no es un objeto JSON |
| #21 | Claves de dos fuentes a la vez | fuente ambigua |
| #22 | Monto `€50.00` con moneda `USD` | conflicto de moneda |

Entre los 7 válidos hay casos que el sistema resuelve: `"refunded"` y un estado ausente (→ `FAILED` con aviso), el monto europeo `"1.234,56"`, una fecha sin hora (→ medianoche UTC) y un estado con espacios (`" Completed "`).

### Errores de archivo

| Archivo | Esperado | Obtenido |
|---|---|---|
| `json_malformado.json` | Mensaje con la línea y columna del error | "el archivo no es un JSON válido (línea 3, columna 3)" |
| `no_es_lista.json` | Aviso de que debe ser una lista | "el JSON debe ser una lista de transacciones" |
| `lista_vacia.json` | Aviso de que no hay transacciones | "no contiene transacciones" y métricas en 0 |
| Archivo inexistente | Mensaje claro, sin colapsar | "no existe el archivo ..." |

### Pruebas manuales

Marcar al completarlas:

- [ ] Recorrí todas las opciones del menú con `transacciones_con_errores.json`.
- [ ] Combiné al menos dos filtros y verifiqué que el conteo coincide con lo esperado.
- [ ] Probé una entrada inválida (letras en un monto, fecha mal escrita) y no se rompió.
- [ ] Creé un archivo JSON propio con datos inventados y revisé el resultado.

---

## ⚠️ Limitaciones conocidas

- **No se convierten monedas:** los totales se muestran por moneda, sin equivalencia entre ellas.
- **Sin nombres de zona horaria:** solo se aceptan fechas con desfase numérico (`+02:00`) o `Z`; las que no tienen zona se asumen UTC.
- **Formato `1,234` ambiguo:** se interpreta como miles (1234.00), no como decimal. Es una convención propuesta, no una certeza.
- **Fechas con barras** se leen siempre día/mes/año; `03/10/2025` es el 3 de octubre.
- **El archivo se carga completo en memoria:** no es ideal para archivos muy grandes.
- **Fechas en epoch** (números) no están soportadas y se marcan como inválidas.

---

*Desarrollado con IA como herramienta de apoyo · KODIGO Academy*
