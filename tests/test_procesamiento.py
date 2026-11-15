"""Pruebas de punta a punta con los archivos de datos. Los valores esperados se calcularon a mano."""
import json
import os
import sys
import tempfile
import unittest
from decimal import Decimal

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, ".."))
import config
import filtros
import metricas
import procesador as pr
from filtros import Filtros

DATOS = os.path.join(AQUI, "..", "datos")
REGLAS = config.cargar_reglas()
D = Decimal


def procesar(nombre):
    return pr.procesar_archivo(os.path.join(DATOS, nombre), REGLAS)


class TestEjemploEnunciado(unittest.TestCase):
    def test_las_tres_fuentes_convergen_al_mismo_formato(self):
        r = procesar("ejemplo_enunciado.json")
        self.assertEqual((len(r.valid), len(r.invalid)), (3, 0))
        esperado = [
            ("tx_001", D("100.50"), "USD", "fuente_A"),
            ("204", D("100.50"), "USD", "fuente_B"),     # 10050 centavos
            ("A-77", D("99.99"), "EUR", "fuente_C"),     # "€99,99"
        ]
        for tx, (id_, monto, moneda, fuente) in zip(r.valid, esperado):
            self.assertEqual((tx.id, tx.amount, tx.currency, tx.source), (id_, monto, moneda, fuente))
            self.assertEqual(tx.timestamp, "2025-03-10T14:22:00Z")
            self.assertEqual(tx.status, "SUCCESS")


class TestDatosValidos(unittest.TestCase):
    def setUp(self):
        self.r = procesar("transacciones_validas.json")

    def test_todas_validas(self):
        self.assertEqual((len(self.r.valid), len(self.r.invalid), len(self.r.avisos)), (12, 0, 0))

    def test_metricas(self):
        m = metricas.calcular(self.r.valid, self.r.invalid, REGLAS.estados)
        self.assertEqual((m.total, m.validas, m.invalidas), (12, 12, 0))
        self.assertEqual(m.por_estado, {"SUCCESS": 6, "FAILED": 3, "PENDING": 3})
        self.assertEqual(m.por_fuente, {"fuente_A": 5, "fuente_B": 4, "fuente_C": 3})
        esperado = {"USD": (6, D("7885.56"), D("1401.00")),
                    "EUR": (3, D("201.23"), D("99.99")),
                    "GBP": (3, D("84.98"), D("39.98"))}
        for moneda, (cant, total, confirmado) in esperado.items():
            fila = m.por_moneda[moneda]
            self.assertEqual((fila["cantidad"], fila["total"], fila["confirmado"]), (cant, total, confirmado), moneda)

    def test_filtros(self):
        v = self.r.valid
        casos = [
            (Filtros(estado="SUCCESS"), 6),
            (Filtros(moneda="EUR"), 3),
            (Filtros(fuente="fuente_B"), 4),
            (Filtros(monto_min=D("1000")), 3),
            (Filtros(monto_max=D("50")), 4),
            (Filtros(fecha_desde="2025-03-12"), 6),
            (Filtros(fecha_hasta="2025-03-11"), 6),
            (Filtros(estado="SUCCESS", moneda="USD"), 3),
            (Filtros(estado="SUCCESS", moneda="USD", monto_min=D("1000")), 1),
            (Filtros(), 12),
            (Filtros(moneda="GBP", estado="PENDING"), 0),
        ]
        for f, cantidad in casos:
            with self.subTest(filtro=f.activos()):
                self.assertEqual(len(filtros.aplicar(v, f)), cantidad)


class TestDatosConErrores(unittest.TestCase):
    def setUp(self):
        self.r = procesar("transacciones_con_errores.json")

    def test_conteos(self):
        self.assertEqual((len(self.r.valid), len(self.r.invalid)), (7, 17))
        self.assertEqual(self.r.total, 24)

    def test_validas_esperadas(self):
        self.assertEqual([t.id for t in self.r.valid], ["e_001", "e_008", "e_009", "301", "A-91", "e_012", "e_013"])
        self.assertEqual([t.status for t in self.r.valid],
                         ["SUCCESS", "FAILED", "FAILED", "SUCCESS", "SUCCESS", "SUCCESS", "SUCCESS"])
        por_id = {t.id: t for t in self.r.valid}
        self.assertEqual(por_id["301"].amount, D("25.00"))                    # 2500 centavos
        self.assertEqual(por_id["e_012"].amount, D("1234.56"))                # "1.234,56"
        self.assertEqual(por_id["e_013"].timestamp, "2025-04-02T00:00:00Z")   # solo fecha
        self.assertEqual(por_id["A-91"].currency, "USD")                      # símbolo $

    def test_decision_estudiante_estado_desconocido_o_ausente(self):
        self.assertEqual([(a.position, a.id) for a in self.r.avisos], [(8, "e_008"), (9, "e_009")])

    def test_invalidas_posiciones_y_motivos(self):
        esperado = {
            2: "monto no numérico", 3: "falta campo obligatorio: amount", 4: "moneda no soportada: XYZ",
            5: "monto no positivo", 6: "monto no positivo", 7: "fecha no reconocida", 10: "id duplicado",
            12: "monto no numérico", 13: "fecha con tipo no soportado", 14: "más de 2 decimales",
            15: "falta campo obligatorio: transaction_id", 16: "moneda no determinable", 18: "fecha no reconocida",
            19: "fuente no reconocida", 20: "no es un objeto", 21: "fuente ambigua", 22: "conflicto de moneda",
        }
        self.assertEqual([i.position for i in self.r.invalid], sorted(esperado))
        for inv in self.r.invalid:
            with self.subTest(posicion=inv.position):
                self.assertTrue(any(esperado[inv.position] in motivo for motivo in inv.reasons), inv.reasons)

    def test_decision_estudiante_las_invalidas_se_separan_con_su_original(self):
        inv = {i.position: i for i in self.r.invalid}
        self.assertEqual(inv[2].raw["amount"], "abc")
        self.assertEqual(inv[20].raw, "esto no es un objeto")
        self.assertNotIn("e_002", [t.id for t in self.r.valid])

    def test_metricas(self):
        m = metricas.calcular(self.r.valid, self.r.invalid, REGLAS.estados)
        self.assertEqual(m.por_estado, {"SUCCESS": 5, "FAILED": 2, "PENDING": 0})
        self.assertEqual(m.por_fuente, {"fuente_A": 5, "fuente_B": 1, "fuente_C": 1})
        self.assertEqual(set(m.por_moneda), {"USD", "EUR"})
        self.assertEqual((m.por_moneda["USD"]["cantidad"], m.por_moneda["USD"]["total"], m.por_moneda["USD"]["confirmado"]),
                         (5, D("2270.00"), D("2230.00")))
        self.assertEqual((m.por_moneda["EUR"]["cantidad"], m.por_moneda["EUR"]["total"], m.por_moneda["EUR"]["confirmado"]),
                         (2, D("1294.56"), D("1234.56")))
        self.assertEqual(round(m.porcentaje_validas, 1), 29.2)
        self.assertEqual(m.motivos_invalidas["monto no positivo"], 2)
        # Los motivos del mismo tipo se agrupan aunque el detalle cambie:
        self.assertEqual(m.motivos_invalidas["monto no numérico"], 2)            # "abc" y el valor booleano
        self.assertEqual(m.motivos_invalidas["falta campo obligatorio"], 2)
        self.assertEqual(m.motivos_invalidas["fecha no reconocida"], 2)
        self.assertEqual(m.motivos_invalidas["fecha con tipo no soportado"], 1)
        self.assertEqual(sum(m.motivos_invalidas.values()), 17)                  # cada inválida tiene 1 motivo


class TestErroresDeArchivo(unittest.TestCase):
    def test_errores(self):
        casos = {
            "no_existe.json": "no existe",
            "json_malformado.json": "no es un JSON válido",
            "no_es_lista.json": "debe ser una lista",
            "": "carpeta",
        }
        for nombre, texto in casos.items():
            with self.subTest(archivo=nombre or "(carpeta)"):
                with self.assertRaises(pr.DatosError) as ctx:
                    pr.cargar_registros(os.path.join(DATOS, nombre))
                self.assertIn(texto, str(ctx.exception))

    def test_lista_vacia(self):
        r = procesar("lista_vacia.json")
        self.assertEqual((r.total, len(r.valid), len(r.invalid)), (0, 0, 0))
        m = metricas.calcular(r.valid, r.invalid, REGLAS.estados)
        self.assertEqual(m.porcentaje_validas, 0.0)


class TestReglas(unittest.TestCase):
    def _datos(self):
        with open(config.RUTA_REGLAS, encoding="utf-8") as f:
            return json.load(f)

    def test_reglas_incompletas_dan_error_claro(self):
        for quitar in ("fuentes", "monedas_soportadas", "formatos_fecha", "validacion"):
            d = self._datos()
            del d[quitar]
            with self.subTest(sin=quitar):
                with self.assertRaises(config.ReglasError):
                    config.Reglas(d)

    def test_estado_desconocido_debe_ser_un_estado_valido(self):
        d = self._datos()
        d["estado_desconocido"] = "QUIEN_SABE"
        with self.assertRaises(config.ReglasError):
            config.Reglas(d)

    def test_alias_repetido_en_dos_estados(self):
        d = self._datos()
        d["mapeo_estados"]["FAILED"].append("ok")
        with self.assertRaises(config.ReglasError):
            config.Reglas(d)

    def test_cambiar_regla_cambia_el_comportamiento(self):
        d = self._datos()
        d["fuentes"]["fuente_B"]["monto_entero_en"] = "unidades"
        r = pr.procesar_archivo(os.path.join(DATOS, "ejemplo_enunciado.json"), config.Reglas(d))
        self.assertEqual(r.valid[1].amount, D("10050.00"))

        d = self._datos()
        d["estado_desconocido"] = "PENDING"
        r = pr.procesar_archivo(os.path.join(DATOS, "transacciones_con_errores.json"), config.Reglas(d))
        self.assertEqual([t.status for t in r.valid if t.id in ("e_008", "e_009")], ["PENDING", "PENDING"])


if __name__ == "__main__":
    unittest.main()
