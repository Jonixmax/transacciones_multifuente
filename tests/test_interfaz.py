"""Pruebas de la interfaz CLI simulando lo que escribiría el usuario."""
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, ".."))
import config
from interfaz import Interfaz

DATOS = os.path.join(AQUI, "..", "datos")
VALIDAS = os.path.join(DATOS, "transacciones_validas.json")
ERRORES = os.path.join(DATOS, "transacciones_con_errores.json")
REGLAS = config.cargar_reglas()


def correr(respuestas, ruta=None):
    """Ejecuta la interfaz con respuestas predefinidas y devuelve todo lo que mostró."""
    it = iter(respuestas)
    def entrada(_mensaje):
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    salida = []
    Interfaz(REGLAS, entrada=entrada, salida=salida.append).ejecutar(ruta)
    return "\n".join(salida)


class TestInterfaz(unittest.TestCase):
    def test_metricas(self):
        out = correr(["1", "0"], VALIDAS)
        for texto in ("Total procesadas ..... 12", "7,885.56", "1,401.00", "201.23", "84.98", "SUCCESS", "fuente_B"):
            self.assertIn(texto, out)

    def test_listado_paginado(self):
        out = correr(["2", "s", "q", "0"], VALIDAS)
        self.assertIn("página 1 de 2", out)
        self.assertIn("página 2 de 2", out)
        self.assertIn("tx_001", out)
        self.assertIn("A-79", out)

    def test_filtrar_por_estado_y_listar(self):
        out = correr(["3", "1", "SUCCESS", "0", "2", "0"], VALIDAS)
        self.assertIn("Mostrando 6 de 12", out)
        self.assertIn("Filtros activos: estado: SUCCESS", out)
        self.assertNotIn("tx_002", out)       # es PENDING

    def test_filtros_combinados_y_limpiar(self):
        out = correr(["3", "1", "SUCCESS", "2", "usd", "4", "1000", "0", "2", "3", "8", "0", "0"], VALIDAS)
        self.assertIn("Coinciden: 1 de 12", out)
        self.assertIn("Mostrando 1 de 12", out)
        self.assertIn("Filtros eliminados", out)

    def test_entradas_invalidas_no_rompen(self):
        out = correr(["x", "3", "4", "abc", "1", "NADA", "6", "2025-99-99", "99", "0", "0"], VALIDAS)
        for texto in ("Opción no válida", "Monto no válido", "Estado no válido", "Fecha no válida"):
            self.assertIn(texto, out)

    def test_ver_invalidas_con_motivo(self):
        out = correr(["4", "q", "0"], ERRORES)
        self.assertIn("página 1 de 2", out)
        self.assertIn("Registro #2", out)
        self.assertIn("monto no numérico: 'abc'", out)

    def test_avisos(self):
        out = correr(["5", "0"], ERRORES)
        self.assertIn("estado no reconocido 'refunded'", out)
        self.assertIn("estado ausente", out)
        out = correr(["5", "0"], VALIDAS)
        self.assertIn("No hay avisos", out)

    def test_buscar_por_id(self):
        out = correr(["6", "E_008", "6", "e_002", "0"], ERRORES)       # no distingue mayúsculas
        self.assertIn("TRANSACCIÓN e_008", out)
        self.assertIn("amount     40.00", out)           # no "40.0"
        self.assertIn("Registro original", out)
        self.assertIn("Aviso: estado no reconocido", out)
        self.assertIn("No hay una transacción válida con id 'e_002'", out)

    def test_ver_reglas_muestra_origen_de_las_decisiones(self):
        out = correr(["7", "0"], VALIDAS)
        self.assertIn("origen: ESTUDIANTE", out)
        self.assertIn("origen: PROPUESTA DE LA IA", out)
        self.assertIn("CENTAVOS", out)

    def test_exportar(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = os.path.join(tmp, "salida")
            out = correr(["8", destino, "0"], ERRORES)
            self.assertIn("Exportado", out)
            with open(os.path.join(destino, "normalizadas.json"), encoding="utf-8") as f:
                self.assertEqual(len(json.load(f)), 7)
            with open(os.path.join(destino, "invalidas.json"), encoding="utf-8") as f:
                self.assertEqual(len(json.load(f)), 17)
            with open(os.path.join(destino, "metricas.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["por_moneda"]["USD"]["total"], 2270.0)

    def test_exportar_en_ruta_imposible(self):
        out = correr(["8", os.path.join(VALIDAS, "no_se_puede"), "0"], VALIDAS)   # VALIDAS es un archivo
        self.assertIn("Error al exportar", out)

    def test_elegir_archivo_por_numero_sin_argumento(self):
        out = correr(["1", "0"])        # el 1.º archivo de datos/ en orden alfabético es ejemplo_enunciado.json
        self.assertIn("ejemplo_enunciado.json", out)
        self.assertIn("3 válidos", out)

    def test_archivo_inexistente_vuelve_a_pedir_y_se_puede_salir(self):
        out = correr(["", ], os.path.join(DATOS, "no_existe.json"))
        self.assertIn("Error: no existe el archivo", out)
        self.assertIn("Hasta luego", out)

    def test_archivo_malo_no_pierde_los_datos_ya_cargados(self):
        out = correr(["9", os.path.join(DATOS, "json_malformado.json"), "1", "0"], VALIDAS)
        self.assertIn("no es un JSON válido", out)
        self.assertIn("Total procesadas ..... 12", out)

    def test_archivo_vacio(self):
        out = correr(["1", "2", "0"], os.path.join(DATOS, "lista_vacia.json"))
        self.assertIn("no contiene transacciones", out)
        self.assertIn("Total procesadas ..... 0", out)
        self.assertIn("No hay registros para mostrar", out)

    def test_cierre_de_entrada_sale_sin_error(self):
        out = correr([], VALIDAS)
        self.assertIn("Hasta luego", out)


if __name__ == "__main__":
    unittest.main()
