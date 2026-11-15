"""MÉTRICAS: total procesadas, válidas vs inválidas, conteo por estado y totales por moneda."""
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict


@dataclass
class Metricas:
    total: int = 0
    validas: int = 0
    invalidas: int = 0
    por_estado: Dict[str, int] = field(default_factory=dict)
    por_fuente: Dict[str, int] = field(default_factory=dict)
    # moneda -> {"cantidad": n, "total": todas las válidas, "confirmado": solo SUCCESS}
    por_moneda: Dict[str, dict] = field(default_factory=dict)
    motivos_invalidas: Dict[str, int] = field(default_factory=dict)

    @property
    def porcentaje_validas(self):
        return (100.0 * self.validas / self.total) if self.total else 0.0


def categoria_motivo(motivo):
    """Agrupa motivos parecidos quitando el detalle que va después de ':', '(' o ';'.

    'monto no positivo: 0'                  -> 'monto no positivo'
    'monto no numérico (valor booleano)'    -> 'monto no numérico'
    """
    return re.split(r"[:(;]", motivo)[0].strip()


def calcular(validas, invalidas, estados):
    m = Metricas(total=len(validas) + len(invalidas), validas=len(validas), invalidas=len(invalidas))
    m.por_estado = {e: 0 for e in estados}
    for tx in validas:
        m.por_estado[tx.status] = m.por_estado.get(tx.status, 0) + 1
        m.por_fuente[tx.source] = m.por_fuente.get(tx.source, 0) + 1
        fila = m.por_moneda.setdefault(tx.currency, {"cantidad": 0, "total": Decimal("0"), "confirmado": Decimal("0")})
        fila["cantidad"] += 1
        fila["total"] += tx.amount
        if tx.status == "SUCCESS":
            fila["confirmado"] += tx.amount
    contador = Counter(categoria_motivo(r) for inv in invalidas for r in inv.reasons)
    m.motivos_invalidas = dict(contador.most_common())
    return m
