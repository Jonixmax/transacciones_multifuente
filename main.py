"""
Explorador de transacciones multifuente.

Uso:
    python main.py                                  -> elegir un archivo de la carpeta datos/
    python main.py datos/transacciones_validas.json

Estructura (separación de responsabilidades):
    reglas.json    reglas de normalización y validación (configuración)
    config.py      carga y comprueba reglas.json
    modelos.py     modelo de datos (esquema normalizado)
    normalizador.py  transformación de montos, moneda, fecha y estado
    validador.py   criterios de validez
    procesador.py  lectura del JSON y orquestación
    metricas.py    métricas   |   filtros.py  filtros de exploración
    interfaz.py    CLI interactiva
"""
import sys

from config import ReglasError, cargar_reglas
from interfaz import Interfaz


def main(argv=None):
    argv = sys.argv if argv is None else argv
    try:
        reglas = cargar_reglas()
    except ReglasError as e:
        print(f"Error en el archivo de reglas: {e}")
        return 1
    Interfaz(reglas).ejecutar(argv[1] if len(argv) > 1 else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
