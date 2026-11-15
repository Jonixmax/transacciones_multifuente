"""
PROCESAMIENTO: orquesta lectura del JSON -> detección de fuente -> normalización
-> validación, y separa el resultado en válidas, inválidas y avisos.
"""
import json

from modelos import Aviso, InvalidRecord, ResultadoProcesamiento, Transaction
from normalizador import detectar_fuente, normalizar
from validador import campos_faltantes, validar


class DatosError(Exception):
    """El archivo de datos no se pudo leer o no tiene la estructura esperada."""


def cargar_registros(ruta):
    """Lee el archivo JSON y devuelve la lista de registros crudos."""
    try:
        with open(ruta, encoding="utf-8-sig") as f:
            datos = json.load(f)
    except FileNotFoundError:
        raise DatosError(f"no existe el archivo '{ruta}'")
    except IsADirectoryError:
        raise DatosError(f"'{ruta}' es una carpeta, no un archivo")
    except PermissionError:
        raise DatosError(f"no tienes permiso para leer '{ruta}'")
    except json.JSONDecodeError as e:
        raise DatosError(f"el archivo no es un JSON válido (línea {e.lineno}, columna {e.colno}): {e.msg}")
    except UnicodeDecodeError:
        raise DatosError("el archivo no se puede leer como texto UTF-8")
    except OSError as e:
        raise DatosError(f"no se pudo abrir '{ruta}': {e}")
    if not isinstance(datos, list):
        raise DatosError("el JSON debe ser una lista de transacciones: [ {...}, {...} ]")
    return datos


def procesar_registros(registros, reglas):
    """Normaliza y valida cada registro. Los inválidos se SEPARAN (decisión del estudiante)."""
    resultado = ResultadoProcesamiento()
    vistos = set()          # (fuente, id) de las transacciones ya aceptadas, para detectar duplicados

    for posicion, raw in enumerate(registros, start=1):
        fuente, motivo = detectar_fuente(raw, reglas)
        if motivo:
            resultado.invalid.append(InvalidRecord(posicion, raw, None, [motivo]))
            continue

        faltan = campos_faltantes(raw, fuente, reglas)
        parcial = normalizar(raw, fuente, reglas)
        razones = [f"falta campo obligatorio: {nombre}" for _, nombre in faltan]
        razones += parcial.errores
        razones += validar(parcial, reglas, vistos, moneda_faltante=any(l == "moneda" for l, _ in faltan))

        if razones:
            resultado.invalid.append(InvalidRecord(posicion, raw, fuente, razones))
            continue

        tx = Transaction(id=parcial.id, amount=parcial.amount, currency=parcial.currency,
                         timestamp=parcial.timestamp, status=parcial.status, source=fuente)
        resultado.valid.append(tx)
        resultado.raw_by_key[(fuente, tx.id)] = raw
        vistos.add((fuente, tx.id))
        for aviso in parcial.avisos:
            resultado.avisos.append(Aviso(posicion, tx.id, aviso))
    return resultado


def procesar_archivo(ruta, reglas):
    return procesar_registros(cargar_registros(ruta), reglas)
