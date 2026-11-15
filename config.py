"""
Carga y validación del archivo de reglas (reglas.json).

Este módulo NO decide nada: solo lee las reglas definidas en reglas.json y comprueba
que el archivo esté completo, para fallar con un mensaje claro si falta algo.
"""
import json
import os
from decimal import Decimal, InvalidOperation

RUTA_REGLAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reglas.json")
UNIDADES_VALIDAS = ("unidades", "centavos")
CLAVES_LOGICAS = ("id", "monto", "moneda", "fecha", "estado")


class ReglasError(Exception):
    """El archivo de reglas no existe, no es JSON válido o está incompleto."""


class Reglas:
    """Reglas ya interpretadas y listas para usar por los demás módulos."""

    def __init__(self, datos):
        try:
            self.campos_esquema = list(datos["esquema_normalizado"]["campos"])
            self.estados = list(datos["esquema_normalizado"]["estados"])
            self.fuentes = dict(datos["fuentes"])
            self.monedas = {str(m).upper() for m in datos["monedas_soportadas"]}
            self.simbolos = dict(datos["simbolos_moneda"])
            self.mapeo_estados = dict(datos["mapeo_estados"])
            self.estado_desconocido = datos["estado_desconocido"]
            self.formatos_fecha = list(datos["formatos_fecha"])
            validacion = datos["validacion"]
            self.monto_min = Decimal(str(validacion["monto_minimo_exclusivo"]))
            self.max_decimales = int(validacion["maximo_decimales"])
            self.rechazar_duplicados = bool(validacion["rechazar_ids_duplicados"])
            self.decisiones = list(datos.get("decisiones", []))
        except (KeyError, TypeError, ValueError, InvalidOperation) as e:
            raise ReglasError(f"reglas.json incompleto o con formato incorrecto: {e!r}")
        self._validar()

    def _validar(self):
        if not self.monedas:
            raise ReglasError("reglas.json: 'monedas_soportadas' no puede estar vacía")
        if not self.formatos_fecha:
            raise ReglasError("reglas.json: 'formatos_fecha' no puede estar vacío")
        if self.estado_desconocido not in self.estados:
            raise ReglasError("reglas.json: 'estado_desconocido' debe ser uno de los estados válidos")
        # Tabla inversa alias -> estado normalizado (se compara sin distinguir mayúsculas)
        self.estado_lookup = {}
        for estado, alias in self.mapeo_estados.items():
            if estado not in self.estados:
                raise ReglasError(f"reglas.json: el estado '{estado}' del mapeo no está en el esquema")
            for a in alias:
                clave = str(a).strip().lower()
                if clave in self.estado_lookup and self.estado_lookup[clave] != estado:
                    raise ReglasError(f"reglas.json: el alias '{a}' está asignado a dos estados distintos")
                self.estado_lookup[clave] = estado
        if not self.fuentes:
            raise ReglasError("reglas.json: debe definir al menos una fuente")
        for nombre, cfg in self.fuentes.items():
            for clave in ("campo_identificador", "campos", "campos_obligatorios", "monto_entero_en"):
                if clave not in cfg:
                    raise ReglasError(f"reglas.json: la fuente '{nombre}' no define '{clave}'")
            for logico in CLAVES_LOGICAS:
                if logico not in cfg["campos"]:
                    raise ReglasError(f"reglas.json: la fuente '{nombre}' no mapea el campo '{logico}'")
            if cfg["monto_entero_en"] not in UNIDADES_VALIDAS:
                raise ReglasError(f"reglas.json: 'monto_entero_en' de '{nombre}' debe ser {UNIDADES_VALIDAS}")
            if cfg["campo_identificador"] != cfg["campos"]["id"]:
                raise ReglasError(f"reglas.json: en '{nombre}' el campo identificador debe coincidir con campos.id")
            for logico in cfg["campos_obligatorios"]:
                if logico not in CLAVES_LOGICAS or not cfg["campos"].get(logico):
                    raise ReglasError(f"reglas.json: '{logico}' no puede ser obligatorio en '{nombre}' (no tiene campo propio)")


def cargar_reglas(ruta=RUTA_REGLAS):
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
    except FileNotFoundError:
        raise ReglasError(f"no se encontró el archivo de reglas '{ruta}'")
    except json.JSONDecodeError as e:
        raise ReglasError(f"reglas.json no es un JSON válido (línea {e.lineno}, columna {e.colno}): {e.msg}")
    except OSError as e:
        raise ReglasError(f"no se pudo leer el archivo de reglas: {e}")
    if not isinstance(datos, dict):
        raise ReglasError("reglas.json debe contener un objeto JSON")
    return Reglas(datos)
