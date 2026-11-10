"""Contratos del mart y decisiones; evita volver a promediar medianas."""
import unittest
import pandas as pd
from src.priorizacion import listas_operativas
from src.validar_cierre import verificar


class CierreTests(unittest.TestCase):
    def test_mart_coincide_con_avisos(self):
        summary = verificar()
        self.assertTrue(summary.n.gt(0).all())

    def test_coexistencia_no_excluye_monitoreo(self):
        base = pd.DataFrame(dict(tipo_operacion_norm=['alquiler'] * 90,
            precio_m2_usd=[10.] * 30 + [20.] * 30 + [30.] * 30,
            en_alcance_territorial=True, precio_m2_usd_fuera_rango_flag=False, comuna_oficial=[1] * 30 + [2] * 30 + [3] * 30,
            moneda_norm='ARS', fuente_norm='portal'))
        comunas = pd.DataFrame(dict(comuna=[1,2,3], n_airbnb=[30,60,90], n_alquiler=[30,60,90],
            airbnb_por_1000_viviendas=[1,2,3], alquiler_por_1000_hogares_inquilinos=[1,2,3]))
        lists, scenarios = listas_operativas(base, comunas)
        first = lists.query("decision == 'monitoreo_temporario' and puesto == 1").iloc[0]
        self.assertEqual(first.comuna, 3)
        self.assertEqual(len(lists), 9)
        self.assertTrue(scenarios.puesto.ge(1).all())


if __name__ == '__main__':
    unittest.main()
