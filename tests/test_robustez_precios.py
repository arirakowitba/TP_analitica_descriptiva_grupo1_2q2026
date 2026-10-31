import unittest
import numpy as np
import pandas as pd
from src.robustez_precios import model_audit, sample


class ModelAuditTests(unittest.TestCase):
    def test_known_positive_association_and_complete_diagnostics(self):
        rng=np.random.default_rng(7)
        n=800
        dm=rng.uniform(0,15,n)
        sup=rng.uniform(25,120,n)
        price=np.exp(7+.04*dm-.1*np.log(sup)+rng.normal(0,.08,n))
        data=pd.DataFrame({
            'id_publicacion':np.arange(n).astype(str),
            'fuente_norm':np.where(np.arange(n)%3==0,'portal_b','portal_a'),
            'coords_en_caba':True,'precio_m2_usd':price,
            'precio_m2_usd_fuera_rango_flag':False,'superficie_ref_m2':sup,
            'ambientes_ref':rng.integers(1,5,n),
            'tipo_operacion_norm':np.where(np.arange(n)<400,'venta','alquiler'),
            'barrio_oficial':['B'+str(i%20) for i in range(n)],
            'dist_transporte_masivo_m':dm*100,'metodo_geo':'rest_calle_altura'})
        sens,diag,influence,residuals,tests,curves=model_audit(data)
        refs=sens[sens.escenario.eq('referencia_t_Gmenos1')]
        self.assertEqual(len(refs),2)
        self.assertTrue(refs.efecto_pct.between(2,6).all())
        self.assertTrue(refs.lo.gt(0).all())
        self.assertEqual(len(diag),2)
        self.assertEqual(len(residuals),n)
        self.assertEqual(len(influence),20)
        self.assertTrue(tests.q_BH.between(0,1).all())
        self.assertEqual(len(curves),12)
        self.assertTrue(np.isfinite(curves[['efecto_pct','lo','hi']]).all().all())
        invalid=data.copy();invalid.loc[0,'precio_m2_usd']=0
        self.assertEqual(len(sample(invalid)),n-1)


if __name__=='__main__':unittest.main()
