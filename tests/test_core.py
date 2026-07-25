"""
tests/test_core.py — Pruebas unitarias para parser, differ y checker

Ejecutar:
    python -m pytest tests/ -v
    # o sin pytest:
    python tests/test_core.py
"""

import csv
import io
import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Asegurar que el directorio raíz esté en el path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import config
from core.parser import (
    _limpiar_rfc,
    _limpiar_nombre,
    _normalizar_situacion,
    _limpiar_fecha,
    registros_a_dict_rfc,
)
from core.differ import comparar, resumen_texto
from core.checker import consultar_rfc


# ─── Fixtures ────────────────────────────────────────────────────────────────

REGISTROS_EJEMPLO = [
    {
        "numero": "1",
        "rfc": "AAA010101AAA",
        "nombre": "EMPRESA FANTASMA SA DE CV",
        "situacion": config.SITUACION_DEFINITIVO,
        "fecha_primera_publicacion": "2023-01-15",
        "numero_oficio": "500-05-2023-00001",
    },
    {
        "numero": "2",
        "rfc": "BBBX800101HDF",
        "nombre": "PERSONA FÍSICA PRESUNTA",
        "situacion": config.SITUACION_PRESUNTO,
        "fecha_primera_publicacion": "2024-06-01",
        "numero_oficio": "500-05-2024-00002",
    },
    {
        "numero": "3",
        "rfc": "CCC010101CCC",
        "nombre": "EMPRESA DESVIRTUADA SC",
        "situacion": config.SITUACION_DESVIRTUADO,
        "fecha_primera_publicacion": "2022-03-20",
        "numero_oficio": "500-05-2022-00003",
    },
]


# ─── Tests: parser ────────────────────────────────────────────────────────────

class TestParser(unittest.TestCase):

    def test_limpiar_rfc_uppercase_y_strip(self):
        self.assertEqual(_limpiar_rfc("  aaa010101aaa  "), "AAA010101AAA")

    def test_limpiar_rfc_ya_correcto(self):
        self.assertEqual(_limpiar_rfc("BBBX800101HDF"), "BBBX800101HDF")

    def test_limpiar_nombre_espacios_multiples(self):
        resultado = _limpiar_nombre("empresa   fantasma   sa  de  cv")
        self.assertEqual(resultado, "EMPRESA FANTASMA SA DE CV")

    def test_normalizar_situacion_definitivo(self):
        for entrada in ["Definitivo", "DEFINITIVO", "  definitivo  "]:
            self.assertEqual(
                _normalizar_situacion(entrada), config.SITUACION_DEFINITIVO
            )

    def test_normalizar_situacion_presunto(self):
        self.assertEqual(
            _normalizar_situacion("Presunto"), config.SITUACION_PRESUNTO
        )

    def test_normalizar_situacion_desvirtuado(self):
        self.assertEqual(
            _normalizar_situacion("Desvirtuado"), config.SITUACION_DESVIRTUADO
        )

    def test_normalizar_situacion_sentencia(self):
        for entrada in ["sentencia favorable", "Sentencia Favorable", "sentencia"]:
            self.assertIn(
                _normalizar_situacion(entrada),
                [config.SITUACION_SENTENCIA, "sentencia"]
            )

    def test_limpiar_fecha_formato_slash(self):
        self.assertEqual(_limpiar_fecha("15/01/2023"), "2023-01-15")

    def test_limpiar_fecha_ya_iso(self):
        self.assertEqual(_limpiar_fecha("2023-01-15"), "2023-01-15")

    def test_limpiar_fecha_invalida_retorna_original(self):
        self.assertEqual(_limpiar_fecha("no-es-fecha"), "no-es-fecha")

    def test_registros_a_dict_rfc_indexa_correctamente(self):
        indice = registros_a_dict_rfc(REGISTROS_EJEMPLO)
        self.assertIn("AAA010101AAA", indice)
        self.assertIn("BBBX800101HDF", indice)
        self.assertIn("CCC010101CCC", indice)
        self.assertEqual(len(indice), 3)

    def test_registros_a_dict_rfc_prioridad_definitivo(self):
        """Si un RFC aparece como presunto y definitivo, debe prevalecer definitivo."""
        duplicados = [
            {**REGISTROS_EJEMPLO[0], "situacion": config.SITUACION_PRESUNTO},
            {**REGISTROS_EJEMPLO[0], "situacion": config.SITUACION_DEFINITIVO},
        ]
        indice = registros_a_dict_rfc(duplicados)
        self.assertEqual(indice["AAA010101AAA"]["situacion"], config.SITUACION_DEFINITIVO)


# ─── Tests: differ ────────────────────────────────────────────────────────────

class TestDiffer(unittest.TestCase):

    def setUp(self):
        self.anterior = registros_a_dict_rfc(REGISTROS_EJEMPLO[:2])  # AAA, BBB
        self.nuevo_igual = registros_a_dict_rfc(REGISTROS_EJEMPLO[:2])
        self.nuevo_con_alta = registros_a_dict_rfc(REGISTROS_EJEMPLO)  # + CCC
        self.nuevo_con_baja = registros_a_dict_rfc([REGISTROS_EJEMPLO[0]])  # solo AAA

    def test_sin_cambios(self):
        diff = comparar(self.anterior, self.nuevo_igual)
        self.assertEqual(len(diff["nuevos"]), 0)
        self.assertEqual(len(diff["cambios"]), 0)
        self.assertEqual(len(diff["bajas"]), 0)
        self.assertEqual(diff["sin_cambio"], 2)

    def test_deteccion_nuevo(self):
        diff = comparar(self.anterior, self.nuevo_con_alta)
        self.assertEqual(len(diff["nuevos"]), 1)
        self.assertEqual(diff["nuevos"][0]["rfc"], "CCC010101CCC")

    def test_deteccion_baja(self):
        diff = comparar(self.anterior, self.nuevo_con_baja)
        self.assertEqual(len(diff["bajas"]), 1)
        self.assertEqual(diff["bajas"][0]["rfc"], "BBBX800101HDF")

    def test_deteccion_cambio_situacion(self):
        anterior = {"AAA010101AAA": {**REGISTROS_EJEMPLO[0], "situacion": config.SITUACION_PRESUNTO}}
        nuevo = {"AAA010101AAA": {**REGISTROS_EJEMPLO[0], "situacion": config.SITUACION_DEFINITIVO}}
        diff = comparar(anterior, nuevo)
        self.assertEqual(len(diff["cambios"]), 1)
        self.assertEqual(diff["cambios"][0]["situacion_anterior"], config.SITUACION_PRESUNTO)
        self.assertEqual(diff["cambios"][0]["situacion_nueva"], config.SITUACION_DEFINITIVO)

    def test_totales_correctos(self):
        diff = comparar(self.anterior, self.nuevo_con_alta)
        self.assertEqual(diff["total_anterior"], 2)
        self.assertEqual(diff["total_nuevo"], 3)

    def test_resumen_texto_generado(self):
        diff = comparar(self.anterior, self.nuevo_con_alta)
        resumen = resumen_texto(diff)
        self.assertIn("SAT 69-B", resumen)
        self.assertIn("CCC010101CCC", resumen)
        self.assertIsInstance(resumen, str)


# ─── Tests: checker ──────────────────────────────────────────────────────────

class TestChecker(unittest.TestCase):

    def test_rfc_no_encontrado_sin_cache(self):
        """Sin listado local, debe retornar encontrado=False sin crashear."""
        with patch("checker._cargar_cache", return_value={}):
            resultado = consultar_rfc("XAXX010101000")
            self.assertFalse(resultado["encontrado"])
            self.assertEqual(resultado["rfc"], "XAXX010101000")

    def test_rfc_encontrado(self):
        indice = registros_a_dict_rfc(REGISTROS_EJEMPLO)
        with patch("checker._cargar_cache", return_value=indice):
            resultado = consultar_rfc("AAA010101AAA")
            self.assertTrue(resultado["encontrado"])
            self.assertEqual(resultado["situacion"], config.SITUACION_DEFINITIVO)
            self.assertEqual(resultado["nombre"], "EMPRESA FANTASMA SA DE CV")

    def test_rfc_normaliza_a_mayusculas(self):
        indice = registros_a_dict_rfc(REGISTROS_EJEMPLO)
        with patch("checker._cargar_cache", return_value=indice):
            resultado = consultar_rfc("aaa010101aaa")
            self.assertTrue(resultado["encontrado"])

    def test_consulta_lote(self):
        from checker import consultar_lote
        indice = registros_a_dict_rfc(REGISTROS_EJEMPLO)
        with patch("checker._cargar_cache", return_value=indice):
            resultados = consultar_lote(["AAA010101AAA", "XAXX010101000"])
            self.assertEqual(len(resultados), 2)
            self.assertTrue(resultados[0]["encontrado"])
            self.assertFalse(resultados[1]["encontrado"])


# ─── Runner ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
