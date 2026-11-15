"""
INTERFAZ: CLI interactiva para explorar las transacciones normalizadas.

Solo se encarga de mostrar y de pedir datos al usuario: toda la lógica de negocio
(normalizar, validar, calcular métricas, filtrar) vive en los otros módulos.
La entrada y la salida se pueden reemplazar (entrada/salida) para probarla sin teclado.
"""
import glob
import json
import os
from decimal import Decimal, InvalidOperation
from datetime import datetime

import filtros as modulo_filtros
import metricas as modulo_metricas
from procesador import DatosError, procesar_archivo

CARPETA_DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
TAM_PAGINA = 10


class SalirInterfaz(Exception):
    """El usuario cerró la entrada (Ctrl+D / Ctrl+Z) o eligió salir."""


def dinero(valor):
    return format(valor, ",.2f")


def corto(texto, ancho):
    texto = str(texto)
    return texto if len(texto) <= ancho else texto[: ancho - 3] + "..."


class Interfaz:
    def __init__(self, reglas, entrada=input, salida=print):
        self.reglas = reglas
        self.entrada = entrada
        self.salida = salida
        self.resultado = None
        self.ruta = None
        self.filtros = modulo_filtros.Filtros()

    # ------------------------------------------------------------------
    # Utilidades de entrada y salida
    # ------------------------------------------------------------------
    def _pedir(self, mensaje):
        try:
            return self.entrada(mensaje).strip()
        except (EOFError, KeyboardInterrupt):
            raise SalirInterfaz()

    def _linea(self, texto=""):
        self.salida(texto)

    def _titulo(self, texto):
        self._linea()
        self._linea("=" * 72)
        self._linea(f" {texto}")
        self._linea("=" * 72)

    # ------------------------------------------------------------------
    # Carga de archivos
    # ------------------------------------------------------------------
    def cargar(self, ruta):
        """Procesa el archivo. Devuelve True si se cargó; si falla, conserva lo anterior."""
        try:
            resultado = procesar_archivo(ruta, self.reglas)
        except DatosError as e:
            self._linea(f"Error: {e}")
            return False
        self.resultado, self.ruta = resultado, ruta
        self.filtros.limpiar()
        if resultado.total == 0:
            self._linea(f"El archivo '{ruta}' no contiene transacciones.")
        else:
            self._linea(f"Archivo cargado: {resultado.total} registros "
                        f"({len(resultado.valid)} válidos, {len(resultado.invalid)} inválidos).")
        return True

    def elegir_archivo(self):
        """Lista los .json de la carpeta datos/ y pide uno. Devuelve la ruta o None si se sale."""
        archivos = sorted(glob.glob(os.path.join(CARPETA_DATOS, "*.json")))
        self._titulo("ELEGIR ARCHIVO DE TRANSACCIONES")
        for i, ruta in enumerate(archivos, start=1):
            self._linea(f"  {i}. {os.path.basename(ruta)}")
        self._linea("  (o escribe la ruta de otro archivo JSON; Enter vacío para salir)")
        while True:
            texto = self._pedir("Número o ruta: ")
            if not texto:
                return None
            if texto.isdigit() and 1 <= int(texto) <= len(archivos):
                return archivos[int(texto) - 1]
            if texto.isdigit():
                self._linea("Número fuera de rango.")
                continue
            return texto.strip('"')

    # ------------------------------------------------------------------
    # Ciclo principal
    # ------------------------------------------------------------------
    def ejecutar(self, ruta=None):
        try:
            if ruta:
                self.cargar(ruta)
            while self.resultado is None:
                ruta = self.elegir_archivo()
                if ruta is None:
                    self._linea("Hasta luego.")
                    return
                self.cargar(ruta)
            self._menu_principal()
        except SalirInterfaz:
            self._linea()
            self._linea("Hasta luego.")

    def _menu_principal(self):
        acciones = {
            "1": self.ver_metricas, "2": self.listar, "3": self.menu_filtros,
            "4": self.ver_invalidas, "5": self.ver_avisos, "6": self.buscar_id,
            "7": self.ver_reglas, "8": self.exportar, "9": self.cambiar_archivo,
        }
        while True:
            self._titulo("EXPLORADOR DE TRANSACCIONES")
            r = self.resultado
            filtros = ", ".join(self.filtros.activos()) or "ninguno"
            self._linea(f" Archivo: {os.path.basename(self.ruta)}")
            self._linea(f" Válidas: {len(r.valid)}  |  Inválidas: {len(r.invalid)}  |  Filtros activos: {filtros}")
            self._linea()
            self._linea("  1. Ver métricas")
            self._linea("  2. Listar transacciones (aplica los filtros activos)")
            self._linea("  3. Filtrar transacciones")
            self._linea("  4. Ver transacciones inválidas (con su motivo)")
            self._linea("  5. Ver avisos de normalización")
            self._linea("  6. Buscar una transacción por ID")
            self._linea("  7. Ver las reglas aplicadas")
            self._linea("  8. Exportar resultados a JSON")
            self._linea("  9. Cargar otro archivo")
            self._linea("  0. Salir")
            opcion = self._pedir("Elige una opción: ")
            if opcion == "0":
                self._linea("Hasta luego.")
                return
            accion = acciones.get(opcion)
            if accion is None:
                self._linea("Opción no válida. Escribe un número del menú.")
            else:
                accion()

    # ------------------------------------------------------------------
    # 1. Métricas
    # ------------------------------------------------------------------
    def ver_metricas(self):
        r = self.resultado
        m = modulo_metricas.calcular(r.valid, r.invalid, self.reglas.estados)
        self._titulo("MÉTRICAS")
        self._linea(f" Total procesadas ..... {m.total}")
        self._linea(f" Válidas .............. {m.validas}  ({m.porcentaje_validas:.1f}%)")
        self._linea(f" Inválidas ............ {m.invalidas}  ({100 - m.porcentaje_validas if m.total else 0:.1f}%)")
        self._linea()
        self._linea(" Por estado (válidas):")
        for estado, cantidad in m.por_estado.items():
            self._linea(f"   {estado:<9} {cantidad}")
        self._linea(" Por fuente (válidas):")
        for fuente, cantidad in sorted(m.por_fuente.items()):
            self._linea(f"   {fuente:<9} {cantidad}")
        self._linea()
        self._linea(" Totales por moneda (solo válidas):")
        if m.por_moneda:
            self._linea(f"   {'Moneda':<8}{'Cant.':>6}{'Total (todas)':>18}{'Confirmado (SUCCESS)':>24}")
            for moneda, fila in sorted(m.por_moneda.items()):
                self._linea(f"   {moneda:<8}{fila['cantidad']:>6}{dinero(fila['total']):>18}{dinero(fila['confirmado']):>24}")
        else:
            self._linea("   (sin transacciones válidas)")
        if m.motivos_invalidas:
            self._linea()
            self._linea(" Motivos de rechazo:")
            for motivo, cantidad in m.motivos_invalidas.items():
                self._linea(f"   {cantidad:>3} x {motivo}")

    # ------------------------------------------------------------------
    # 2. Listado paginado
    # ------------------------------------------------------------------
    def _paginar(self, items, formatear, titulo, encabezado=None):
        if not items:
            self._linea("No hay registros para mostrar.")
            return
        paginas = (len(items) + TAM_PAGINA - 1) // TAM_PAGINA
        pagina = 0
        while True:
            self._titulo(f"{titulo}  (página {pagina + 1} de {paginas})")
            if encabezado:
                self._linea(encabezado)
            for item in items[pagina * TAM_PAGINA:(pagina + 1) * TAM_PAGINA]:
                for linea in formatear(item):
                    self._linea(linea)
            if paginas == 1:
                return
            orden = self._pedir("[S]iguiente, [A]nterior, [Q] volver: ").lower()
            if orden in ("s", ""):
                pagina = min(pagina + 1, paginas - 1)
            elif orden == "a":
                pagina = max(pagina - 1, 0)
            elif orden == "q":
                return
            else:
                self._linea("Escribe S, A o Q.")

    @staticmethod
    def _fila_tx(tx):
        return [f" {corto(tx.id, 10):<10} {tx.source:<9} {dinero(tx.amount):>13} {tx.currency:<4} {tx.status:<8} {tx.timestamp}"]

    def listar(self):
        r = self.resultado
        visibles = modulo_filtros.aplicar(r.valid, self.filtros)
        filtros = ", ".join(self.filtros.activos()) or "ninguno"
        encabezado = f" {'ID':<10} {'FUENTE':<9} {'MONTO':>13} {'MON.':<4} {'ESTADO':<8} FECHA (UTC)\n" + " " + "-" * 68
        self._linea()
        self._linea(f"Filtros activos: {filtros}  |  Mostrando {len(visibles)} de {len(r.valid)} transacciones válidas")
        self._paginar(visibles, self._fila_tx, "TRANSACCIONES NORMALIZADAS", encabezado)
        if visibles:
            totales = {}
            for tx in visibles:
                totales[tx.currency] = totales.get(tx.currency, Decimal("0")) + tx.amount
            resumen = "  ".join(f"{m} {dinero(t)}" for m, t in sorted(totales.items()))
            self._linea(f" Suma de lo mostrado por moneda: {resumen}")

    # ------------------------------------------------------------------
    # 3. Filtros
    # ------------------------------------------------------------------
    def menu_filtros(self):
        while True:
            visibles = modulo_filtros.aplicar(self.resultado.valid, self.filtros)
            self._titulo("FILTROS")
            self._linea(f" Activos: {', '.join(self.filtros.activos()) or 'ninguno'}")
            self._linea(f" Coinciden: {len(visibles)} de {len(self.resultado.valid)} transacciones válidas")
            self._linea()
            self._linea("  1. Estado          5. Monto máximo")
            self._linea("  2. Moneda          6. Fecha desde (AAAA-MM-DD)")
            self._linea("  3. Fuente          7. Fecha hasta (AAAA-MM-DD)")
            self._linea("  4. Monto mínimo    8. Limpiar todos los filtros")
            self._linea("  0. Volver al menú  (en cada filtro, Enter vacío lo quita)")
            opcion = self._pedir("Elige un filtro: ")
            if opcion == "0":
                return
            if opcion == "8":
                self.filtros.limpiar()
                self._linea("Filtros eliminados.")
            elif opcion in ("1", "2", "3", "4", "5", "6", "7"):
                self._editar_filtro(opcion)
            else:
                self._linea("Opción no válida.")

    def _editar_filtro(self, opcion):
        f = self.filtros
        if opcion == "1":
            valor = self._pedir(f"Estado ({'/'.join(self.reglas.estados)}): ").upper()
            if not valor:
                f.estado = None
            elif valor in self.reglas.estados:
                f.estado = valor
            else:
                self._linea("Estado no válido.")
        elif opcion == "2":
            valor = self._pedir(f"Moneda ({'/'.join(sorted(self.reglas.monedas))}): ").upper()
            if not valor:
                f.moneda = None
            elif valor in self.reglas.monedas:
                f.moneda = valor
            else:
                self._linea("Moneda no soportada.")
        elif opcion == "3":
            valor = self._pedir(f"Fuente ({'/'.join(sorted(self.reglas.fuentes))}): ")
            coincidencias = {n.lower(): n for n in self.reglas.fuentes}
            if not valor:
                f.fuente = None
            elif valor.lower() in coincidencias:
                f.fuente = coincidencias[valor.lower()]
            else:
                self._linea("Fuente no reconocida.")
        elif opcion in ("4", "5"):
            etiqueta = "mínimo" if opcion == "4" else "máximo"
            valor = self._pedir(f"Monto {etiqueta}: ")
            if not valor:
                setattr(f, "monto_min" if opcion == "4" else "monto_max", None)
                return
            try:
                numero = Decimal(valor.replace(",", "."))
                if not numero.is_finite():
                    raise InvalidOperation
            except InvalidOperation:
                self._linea("Monto no válido: escribe un número, por ejemplo 100 o 99.50.")
                return
            setattr(f, "monto_min" if opcion == "4" else "monto_max", numero)
            if f.monto_min is not None and f.monto_max is not None and f.monto_min > f.monto_max:
                self._linea("Aviso: el monto mínimo es mayor que el máximo; no habrá resultados.")
        else:
            etiqueta = "desde" if opcion == "6" else "hasta"
            valor = self._pedir(f"Fecha {etiqueta} (AAAA-MM-DD): ")
            campo = "fecha_desde" if opcion == "6" else "fecha_hasta"
            if not valor:
                setattr(f, campo, None)
                return
            try:
                datetime.strptime(valor, "%Y-%m-%d")
            except ValueError:
                self._linea("Fecha no válida: usa el formato AAAA-MM-DD (por ejemplo 2025-03-10).")
                return
            setattr(f, campo, valor)

    # ------------------------------------------------------------------
    # 4 y 5. Inválidas y avisos
    # ------------------------------------------------------------------
    def ver_invalidas(self):
        def formatear(inv):
            origen = inv.source or "fuente desconocida"
            lineas = [f" Registro #{inv.position} ({origen})"]
            lineas += [f"    - {motivo}" for motivo in inv.reasons]
            lineas.append(f"    original: {corto(json.dumps(inv.raw, ensure_ascii=False), 62)}")
            return lineas
        self._paginar(self.resultado.invalid, formatear, "TRANSACCIONES INVÁLIDAS (separadas)")

    def ver_avisos(self):
        def formatear(aviso):
            return [f" Registro #{aviso.position} (id {aviso.id}): {aviso.message}"]
        if not self.resultado.avisos:
            self._linea("No hay avisos: ninguna transacción necesitó una decisión automática.")
            return
        self._paginar(self.resultado.avisos, formatear, "AVISOS DE NORMALIZACIÓN")

    # ------------------------------------------------------------------
    # 6. Búsqueda por ID
    # ------------------------------------------------------------------
    def buscar_id(self):
        buscado = self._pedir("ID a buscar: ").lower()
        if not buscado:
            return
        encontradas = [tx for tx in self.resultado.valid if tx.id.lower() == buscado]
        if not encontradas:
            self._linea(f"No hay una transacción válida con id '{buscado}'. "
                        "Si el registro existe, revisa la lista de inválidas (opción 4).")
            return
        for tx in encontradas:
            self._titulo(f"TRANSACCIÓN {tx.id}")
            self._linea(" Normalizada:")
            for campo, valor in tx.to_dict().items():
                if campo == "amount":
                    valor = f"{tx.amount:.2f}"       # dinero siempre con 2 decimales (no 40.0)
                self._linea(f"   {campo:<10} {valor}")
            original = self.resultado.raw_by_key.get((tx.source, tx.id))
            self._linea(" Registro original:")
            self._linea("   " + json.dumps(original, ensure_ascii=False))
            for aviso in self.resultado.avisos:
                if aviso.id == tx.id:
                    self._linea(f" Aviso: {aviso.message}")

    # ------------------------------------------------------------------
    # 7. Reglas
    # ------------------------------------------------------------------
    def ver_reglas(self):
        rg = self.reglas
        self._titulo("REGLAS APLICADAS (reglas.json)")
        self._linea(f" Estados válidos: {', '.join(rg.estados)}   |   Estado desconocido -> {rg.estado_desconocido}")
        self._linea(f" Monedas soportadas: {', '.join(sorted(rg.monedas))}")
        self._linea(" Mapeo de estados:")
        for estado, alias in rg.mapeo_estados.items():
            self._linea(f"   {estado:<8} <- {', '.join(alias)}")
        self._linea(" Formatos de fecha aceptados:")
        for formato in rg.formatos_fecha:
            self._linea(f"   {formato}")
        for origen in ("ESTUDIANTE", "PROPUESTA DE LA IA"):
            self._linea()
            self._linea(f" Decisiones — origen: {origen}")
            for d in rg.decisiones:
                if d["origen"].startswith(origen):
                    self._linea(f"   - {d['regla']}")

    # ------------------------------------------------------------------
    # 8. Exportar y 9. Cambiar archivo
    # ------------------------------------------------------------------
    def exportar(self):
        carpeta = self._pedir("Carpeta de salida (Enter = 'salida'): ") or "salida"
        r = self.resultado
        m = modulo_metricas.calcular(r.valid, r.invalid, self.reglas.estados)
        metricas = {
            "total": m.total, "validas": m.validas, "invalidas": m.invalidas,
            "por_estado": m.por_estado, "por_fuente": m.por_fuente,
            "por_moneda": {mon: {"cantidad": f["cantidad"], "total": float(f["total"]),
                                 "confirmado": float(f["confirmado"])} for mon, f in m.por_moneda.items()},
            "motivos_invalidas": m.motivos_invalidas,
        }
        contenido = {
            "normalizadas.json": [tx.to_dict() for tx in r.valid],
            "invalidas.json": [inv.to_dict() for inv in r.invalid],
            "metricas.json": metricas,
        }
        try:
            os.makedirs(carpeta, exist_ok=True)
            for nombre, datos in contenido.items():
                with open(os.path.join(carpeta, nombre), "w", encoding="utf-8") as f:
                    json.dump(datos, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self._linea(f"Error al exportar: {e}")
            return
        self._linea(f"Exportado en '{carpeta}': normalizadas.json, invalidas.json y metricas.json")

    def cambiar_archivo(self):
        ruta = self.elegir_archivo()
        if ruta:
            self.cargar(ruta)
