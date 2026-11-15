"""FILTROS: criterios de exploración sobre las transacciones normalizadas."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class Filtros:
    estado: Optional[str] = None
    moneda: Optional[str] = None
    fuente: Optional[str] = None
    monto_min: Optional[Decimal] = None
    monto_max: Optional[Decimal] = None
    fecha_desde: Optional[str] = None     # 'AAAA-MM-DD'
    fecha_hasta: Optional[str] = None     # 'AAAA-MM-DD'

    def activos(self):
        nombres = {"estado": "estado", "moneda": "moneda", "fuente": "fuente", "monto_min": "monto >=",
                   "monto_max": "monto <=", "fecha_desde": "desde", "fecha_hasta": "hasta"}
        return [f"{etiqueta}: {getattr(self, campo)}" for campo, etiqueta in nombres.items()
                if getattr(self, campo) is not None]

    def limpiar(self):
        for campo in self.__dataclass_fields__:
            setattr(self, campo, None)


def aplicar(transacciones, f):
    """Devuelve las transacciones que cumplen TODOS los filtros activos."""
    salida = []
    for tx in transacciones:
        if f.estado and tx.status != f.estado:
            continue
        if f.moneda and tx.currency != f.moneda:
            continue
        if f.fuente and tx.source != f.fuente:
            continue
        if f.monto_min is not None and tx.amount < f.monto_min:
            continue
        if f.monto_max is not None and tx.amount > f.monto_max:
            continue
        # Los timestamps tienen formato fijo (UTC), así que se pueden comparar como texto.
        if f.fecha_desde and tx.timestamp < f"{f.fecha_desde}T00:00:00Z":
            continue
        if f.fecha_hasta and tx.timestamp > f"{f.fecha_hasta}T23:59:59Z":
            continue
        salida.append(tx)
    return salida
