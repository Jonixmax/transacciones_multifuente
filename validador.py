"""
VALIDACIÓN: decide si una transacción es válida o debe separarse como inválida.

Los criterios de validez salen de reglas.json (y fueron definidos por el estudiante
o propuestos por la IA y confirmados). Cada motivo de rechazo se registra para que
la interfaz pueda mostrar POR QUÉ se rechazó un registro.
"""
from normalizador import es_vacio


def campos_faltantes(raw, fuente, reglas):
    """Lista de (nombre_lógico, nombre_en_el_registro) de los campos obligatorios ausentes o vacíos."""
    cfg = reglas.fuentes[fuente]
    faltan = []
    for logico in cfg["campos_obligatorios"]:
        nombre = cfg["campos"][logico]
        if es_vacio(raw.get(nombre)):
            faltan.append((logico, nombre))
    return faltan


def validar(parcial, reglas, vistos, moneda_faltante=False):
    """Aplica los criterios de validez a un registro ya normalizado. Devuelve la lista de motivos."""
    razones = []

    if parcial.amount is not None and parcial.amount <= reglas.monto_min:
        razones.append(f"monto no positivo: {parcial.amount}")

    if parcial.currency is None:
        if not moneda_faltante:    # si ya se informó como campo obligatorio faltante, no se repite
            razones.append("moneda no determinable: no hay código de moneda ni símbolo en el monto")
    elif parcial.currency not in reglas.monedas:
        razones.append(f"moneda no soportada: {parcial.currency}")

    if parcial.status not in reglas.estados:
        razones.append(f"estado fuera del esquema: {parcial.status}")

    if reglas.rechazar_duplicados and parcial.id is not None and (parcial.source, parcial.id) in vistos:
        razones.append(f"id duplicado: {parcial.id} ya existe en {parcial.source}")

    return razones
