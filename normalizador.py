"""
NORMALIZACIÓN: convierte cada registro de su formato original al esquema común.

Este módulo solo TRANSFORMA (montos, moneda, fecha, estado). No decide si una
transacción es válida: eso lo hace validador.py. Las reglas salen de reglas.json.
Cuando un valor no se puede convertir, se registra el motivo y se sigue con los
demás campos, para informar todos los problemas de un registro de una vez.
"""
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional


def es_vacio(valor):
    """True si el valor es None o un texto vacío / solo espacios."""
    return valor is None or (isinstance(valor, str) and not valor.strip())


# --------------------------------------------------------------------------
# Detección de la fuente
# --------------------------------------------------------------------------
def detectar_fuente(raw, reglas):
    """Devuelve (nombre_fuente, None) o (None, motivo_de_rechazo).

    Se identifica por la clave que solo existe en esa fuente (id, transaction_id, ref).
    """
    if not isinstance(raw, dict):
        return None, "el registro no es un objeto JSON"
    candidatas = [n for n, cfg in reglas.fuentes.items() if cfg["campo_identificador"] in raw]
    claves = ", ".join(cfg["campo_identificador"] for cfg in reglas.fuentes.values())
    if not candidatas:
        return None, f"fuente no reconocida: no contiene ninguna clave identificadora ({claves})"
    if len(candidatas) > 1:
        return None, f"fuente ambigua: contiene claves de varias fuentes ({', '.join(candidatas)})"
    return candidatas[0], None


# --------------------------------------------------------------------------
# Conversión del monto
# --------------------------------------------------------------------------
def _grupos_de_miles_validos(texto, separador):
    """'1.234.567' es válido (grupos de 3); '12.34.567' no."""
    grupos = texto.split(separador)
    return 1 <= len(grupos[0]) <= 3 and all(len(g) == 3 for g in grupos[1:])


def _a_texto_decimal(t, original):
    """Convierte '1.234,56' / '1,234.56' / '99,99' en un texto con punto decimal."""
    hay_punto, hay_coma = "." in t, "," in t
    if hay_punto and hay_coma:
        decimal = "." if t.rfind(".") > t.rfind(",") else ","
        miles = "," if decimal == "." else "."
        entero, _, fraccion = t.rpartition(decimal)
        if miles in fraccion or not _grupos_de_miles_validos(entero, miles):
            raise ValueError(f"formato de monto ambiguo: '{original}'")
        return entero.replace(miles, "") + "." + fraccion
    if hay_coma:
        partes = t.split(",")
        if len(partes) == 2 and len(partes[1]) in (1, 2):      # coma decimal: 99,99
            return partes[0] + "." + partes[1]
        if _grupos_de_miles_validos(t, ","):                    # miles: 1,234
            return t.replace(",", "")
        raise ValueError(f"formato de monto ambiguo: '{original}'")
    if hay_punto:
        if t.count(".") == 1:                                   # un solo punto = decimal
            return t
        if _grupos_de_miles_validos(t, "."):                    # miles: 1.234.567
            return t.replace(".", "")
        raise ValueError(f"formato de monto ambiguo: '{original}'")
    return t


def _verificar_decimales(monto, reglas):
    """Exige a lo sumo N decimales; no se redondea en silencio."""
    paso = Decimal(1).scaleb(-reglas.max_decimales)
    cuantizado = monto.quantize(paso)
    if cuantizado != monto:
        raise ValueError(f"monto con más de {reglas.max_decimales} decimales: {monto}")
    return cuantizado


def parsear_monto(valor, cfg_fuente, reglas):
    """Devuelve (Decimal, símbolo_de_moneda_o_None). Lanza ValueError si no se puede."""
    if isinstance(valor, bool):                       # bool es subclase de int: se rechaza aparte
        raise ValueError("monto no numérico (valor booleano)")
    if isinstance(valor, int):
        monto = Decimal(valor)
        if cfg_fuente["monto_entero_en"] == "centavos":    # DECISIÓN DEL ESTUDIANTE
            monto = monto / Decimal(100)
        return _verificar_decimales(monto, reglas), None
    if isinstance(valor, float):
        if not math.isfinite(valor):
            raise ValueError("monto no numérico (NaN o infinito)")
        return _verificar_decimales(Decimal(str(valor)), reglas), None
    if isinstance(valor, str):
        texto = valor.strip()
        simbolos = {mon for s, mon in reglas.simbolos.items() if s in texto}
        if len(simbolos) > 1:
            raise ValueError(f"monto con símbolos de moneda contradictorios: '{valor}'")
        for s in reglas.simbolos:
            texto = texto.replace(s, "")
        texto = texto.replace(" ", "").replace("\u00a0", "")
        if not re.fullmatch(r"[+-]?[\d.,]+", texto) or not re.search(r"\d", texto):
            raise ValueError(f"monto no numérico: '{valor}'")
        signo = -1 if texto.startswith("-") else 1
        texto = texto.lstrip("+-")
        try:
            monto = Decimal(_a_texto_decimal(texto, valor)) * signo
        except InvalidOperation:
            raise ValueError(f"monto no numérico: '{valor}'")
        return _verificar_decimales(monto, reglas), (simbolos.pop() if simbolos else None)
    raise ValueError(f"monto con tipo no soportado ({type(valor).__name__})")


# --------------------------------------------------------------------------
# Conversión de fecha, estado e id
# --------------------------------------------------------------------------
def parsear_fecha(valor, reglas):
    """Devuelve la fecha en ISO-8601 UTC ('2025-03-10T14:22:00Z') o lanza ValueError."""
    if not isinstance(valor, str):
        raise ValueError(f"fecha con tipo no soportado ({type(valor).__name__}); se esperaba texto")
    texto = valor.strip()
    for formato in reglas.formatos_fecha:
        try:
            fecha = datetime.strptime(texto, formato)
        except ValueError:
            continue
        if fecha.tzinfo is not None:
            fecha = fecha.astimezone(timezone.utc)
        else:
            fecha = fecha.replace(tzinfo=timezone.utc)    # sin zona horaria se asume UTC
        return fecha.strftime("%Y-%m-%dT%H:%M:%SZ")
    raise ValueError(f"fecha no reconocida: '{valor}'")


def mapear_estado(valor, reglas):
    """Devuelve (estado_normalizado, aviso_o_None). Desconocido o ausente -> estado_desconocido."""
    por_defecto = reglas.estado_desconocido            # DECISIÓN DEL ESTUDIANTE: FAILED
    if es_vacio(valor):
        return por_defecto, f"estado ausente: se asignó {por_defecto}"
    estado = reglas.estado_lookup.get(str(valor).strip().lower())
    if estado:
        return estado, None
    return por_defecto, f"estado no reconocido '{valor}': se asignó {por_defecto}"


def normalizar_id(valor):
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise ValueError(f"id con tipo no soportado ({type(valor).__name__})")
    return str(valor).strip()


# --------------------------------------------------------------------------
# Normalización de un registro completo
# --------------------------------------------------------------------------
@dataclass
class Parcial:
    """Resultado de normalizar un registro. Un campo queda en None si faltaba o falló."""
    source: str
    id: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    timestamp: Optional[str] = None
    status: Optional[str] = None
    errores: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)


def normalizar(raw, fuente, reglas):
    """Transforma un registro de la fuente dada al esquema común."""
    cfg = reglas.fuentes[fuente]
    campos = cfg["campos"]
    p = Parcial(source=fuente)

    valor = raw.get(campos["id"])
    if not es_vacio(valor):
        try:
            p.id = normalizar_id(valor)
        except ValueError as e:
            p.errores.append(str(e))

    simbolo = None
    valor = raw.get(campos["monto"])
    if not es_vacio(valor):
        try:
            p.amount, simbolo = parsear_monto(valor, cfg, reglas)
        except ValueError as e:
            p.errores.append(str(e))

    codigo = None
    campo_moneda = campos.get("moneda")
    if campo_moneda and not es_vacio(raw.get(campo_moneda)):
        valor_moneda = raw[campo_moneda]
        if isinstance(valor_moneda, str):
            codigo = valor_moneda.strip().upper()
        else:
            p.errores.append(f"moneda con tipo no soportado ({type(valor_moneda).__name__})")
    if codigo and simbolo and simbolo != codigo:
        p.errores.append(f"conflicto de moneda: el monto indica {simbolo} pero el campo de moneda indica {codigo}")
    p.currency = codigo or simbolo

    valor = raw.get(campos["fecha"])
    if not es_vacio(valor):
        try:
            p.timestamp = parsear_fecha(valor, reglas)
        except ValueError as e:
            p.errores.append(str(e))

    p.status, aviso = mapear_estado(raw.get(campos["estado"]), reglas)
    if aviso:
        p.avisos.append(aviso)
    return p
