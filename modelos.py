"""Modelo de datos: la transacción normalizada y los resultados del procesamiento."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Transaction:
    """Transacción en el esquema normalizado (los 6 campos del enunciado).

    amount se guarda como Decimal para sumar sin errores de redondeo; al exportar
    a JSON se convierte a número con 2 decimales.
    """
    id: str
    amount: Decimal
    currency: str
    timestamp: str      # ISO-8601 en UTC, por ejemplo 2025-03-10T14:22:00Z
    status: str         # SUCCESS | FAILED | PENDING
    source: str

    def to_dict(self):
        return {
            "id": self.id,
            "amount": float(self.amount),
            "currency": self.currency,
            "timestamp": self.timestamp,
            "status": self.status,
            "source": self.source,
        }


@dataclass
class InvalidRecord:
    """Registro rechazado: se conserva el original y TODOS los motivos detectados."""
    position: int                  # posición en el archivo (desde 1)
    raw: Any
    source: Optional[str]
    reasons: List[str]

    def to_dict(self):
        return {"posicion": self.position, "fuente": self.source,
                "motivos": self.reasons, "registro_original": self.raw}


@dataclass
class Aviso:
    """Registro válido que requirió una decisión automática (p. ej. estado → FAILED)."""
    position: int
    id: str
    message: str


@dataclass
class ResultadoProcesamiento:
    valid: List[Transaction] = field(default_factory=list)
    invalid: List[InvalidRecord] = field(default_factory=list)
    avisos: List[Aviso] = field(default_factory=list)
    raw_by_key: Dict[Tuple[str, str], Any] = field(default_factory=dict)   # (fuente, id) -> original

    @property
    def total(self):
        return len(self.valid) + len(self.invalid)
