"""Pruebas de normalización: montos, fechas, estados y detección de fuente."""
import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
import normalizador as nz

REGLAS = config.cargar_reglas()
A, B, C = (REGLAS.fuentes[n] for n in ("fuente_A", "fuente_B", "fuente_C"))
D = Decimal


class TestMonto(unittest.TestCase):
    def test_formatos_validos(self):
        casos = [
            ("100.50", A, D("100.50"), None),
            ("€99,99", C, D("99.99"), "EUR"),
            ("$1,234.56", C, D("1234.56"), "USD"),
            ("1.234,56", A, D("1234.56"), None),
            ("£45,00", C, D("45.00"), "GBP"),
            ("1,234", A, D("1234.00"), None),            # coma con 3 dígitos = miles (propuesta de la IA)
            ("1.234.567", A, D("1234567.00"), None),
            ("2025", A, D("2025.00"), None),
            ("-20.00", A, D("-20.00"), None),            # se convierte; la validación lo rechaza después
            (99.9, A, D("99.90"), None),                 # float = unidades
            (10050, A, D("10050.00"), None),             # entero en fuente A = unidades
        ]
        for valor, cfg, esperado, simbolo in casos:
            with self.subTest(valor=valor):
                monto, sim = nz.parsear_monto(valor, cfg, REGLAS)
                self.assertEqual(monto, esperado)
                self.assertEqual(sim, simbolo)

    def test_decision_estudiante_entero_fuente_B_son_centavos(self):
        self.assertEqual(nz.parsear_monto(10050, B, REGLAS)[0], D("100.50"))
        self.assertEqual(nz.parsear_monto(10051, B, REGLAS)[0], D("100.51"))
        self.assertEqual(nz.parsear_monto(500000, B, REGLAS)[0], D("5000.00"))

    def test_en_fuente_B_los_textos_siguen_siendo_unidades(self):
        self.assertEqual(nz.parsear_monto("100.50", B, REGLAS)[0], D("100.50"))

    def test_montos_invalidos(self):
        for valor in ("abc", "", "€", "--5", True, float("nan"), float("inf"), "12.345", "1,23,45.6", "€$10", [], {}):
            with self.subTest(valor=valor):
                with self.assertRaises(ValueError):
                    nz.parsear_monto(valor, A, REGLAS)


class TestFecha(unittest.TestCase):
    def test_formatos_validos(self):
        casos = {
            "2025-03-10 14:22:00": "2025-03-10T14:22:00Z",
            "10/03/2025 14:22": "2025-03-10T14:22:00Z",              # barras = día/mes/año
            "2025-03-10T14:22:00Z": "2025-03-10T14:22:00Z",
            "2025-03-11T10:00:00+02:00": "2025-03-11T08:00:00Z",     # se convierte a UTC
            "2025-04-02": "2025-04-02T00:00:00Z",                    # solo fecha = medianoche
            "2025-03-10T14:22:00.123Z": "2025-03-10T14:22:00Z",
            "  2025-03-10 14:22:00  ": "2025-03-10T14:22:00Z",
            "29/02/2024 12:00": "2024-02-29T12:00:00Z",              # año bisiesto
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(nz.parsear_fecha(texto, REGLAS), esperado)

    def test_fechas_invalidas(self):
        for valor in ("31/02/2025 10:30", "not a date", "2025-13-45", "29/02/2025 12:00", 1743500000, None, 20250310):
            with self.subTest(valor=valor):
                with self.assertRaises(ValueError):
                    nz.parsear_fecha(valor, REGLAS)


class TestEstado(unittest.TestCase):
    def test_estados_reconocidos(self):
        casos = {"completed": "SUCCESS", "OK": "SUCCESS", " Completed ": "SUCCESS", "success": "SUCCESS",
                 "PENDING": "PENDING", "processing": "PENDING", "failed": "FAILED", "declined": "FAILED"}
        for valor, esperado in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(nz.mapear_estado(valor, REGLAS), (esperado, None))

    def test_decision_estudiante_desconocido_o_ausente_es_FAILED_con_aviso(self):
        for valor in ("refunded", "???", None, "", "   "):
            with self.subTest(valor=valor):
                estado, aviso = nz.mapear_estado(valor, REGLAS)
                self.assertEqual(estado, "FAILED")
                self.assertIsNotNone(aviso)


class TestFuente(unittest.TestCase):
    def test_deteccion(self):
        self.assertEqual(nz.detectar_fuente({"id": "x"}, REGLAS), ("fuente_A", None))
        self.assertEqual(nz.detectar_fuente({"transaction_id": 1}, REGLAS), ("fuente_B", None))
        self.assertEqual(nz.detectar_fuente({"ref": "r"}, REGLAS), ("fuente_C", None))

    def test_rechazos(self):
        self.assertIn("no reconocida", nz.detectar_fuente({"foo": 1}, REGLAS)[1])
        self.assertIn("ambigua", nz.detectar_fuente({"id": 1, "ref": 2}, REGLAS)[1])
        for no_objeto in ("texto", 5, None, [1, 2]):
            self.assertIn("no es un objeto", nz.detectar_fuente(no_objeto, REGLAS)[1])


if __name__ == "__main__":
    unittest.main()
