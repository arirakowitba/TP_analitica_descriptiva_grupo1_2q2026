import unittest
import numpy as np
import pandas as pd
from src.robustez import bh, association, moran, two_groups, pca_bootstrap, territorial_loo, cluster_sensitivity, transform_urban


class RobustnessTests(unittest.TestCase):
    def test_bh_keeps_nan_and_order(self):
        np.testing.assert_allclose(bh([.03, np.nan, .01, .8]), [.045, np.nan, .03, .8])

    def test_null_degenerate_is_not_discovery(self):
        result = association(np.ones(15), np.arange(15), n_boot=30, n_perm=49)
        self.assertTrue(np.isnan(result['p_perm']))
        self.assertEqual(result['n'], 15)

    def test_partial_reduces_known_confounding(self):
        rng = np.random.default_rng(2)
        c = rng.normal(size=150)
        x, y = c+rng.normal(0,.2,150), c+rng.normal(0,.2,150)
        raw = association(x,y,n_boot=30,n_perm=49)
        partial = association(x,y,controls=c,n_boot=30,n_perm=49)
        self.assertGreater(raw['rho'],.8)
        self.assertLess(abs(partial['rho']),.3)

    def test_singleton_no_asymptotic_test(self):
        self.assertTrue(np.isnan(two_groups([1],np.arange(10))['p_mw']))

    def test_spatial_constant_not_estimable(self):
        self.assertTrue(np.isnan(moran(np.ones(8),np.ones((8,2)))['p_perm']))

    def test_pca_alignment_has_finite_intervals(self):
        rng=np.random.default_rng(4)
        x=pd.DataFrame(rng.normal(size=(30,4)),columns=list('abcd'))
        load,variance,angles=pca_bootstrap(x,n_boot=15)
        self.assertEqual(len(load),12)
        self.assertTrue(np.isfinite(angles).all())
        self.assertTrue((load.lo<=load.hi).all())

    def test_loo_excludes_target_and_reports_unseen_commune(self):
        rng=np.random.default_rng(1)
        x=pd.DataFrame(rng.normal(size=(16,4)))
        y=pd.DataFrame({'target':np.arange(16,dtype=float)})
        result=territorial_loo(x,y,np.arange(16),k_values=(2,))
        global_rows=result[result.modelo.eq('global')].set_index('barrio')
        self.assertAlmostEqual(global_rows.loc[0,'predicho'],np.median(np.log1p(np.arange(1,16))))
        self.assertTrue(result[result.modelo.eq('comuna')].fallback_global.all())

    def test_sensitivity_reference_reproduces_identical_fit(self):
        from sklearn.cluster import KMeans
        from sklearn.decomposition import PCA
        frame=pd.DataFrame(np.random.default_rng(1).normal(size=(25,3)),columns=list('abc'))
        x,_=transform_urban(frame)
        z=PCA(n_components=3).fit_transform(x)
        labels=KMeans(n_clusters=3,n_init=50,random_state=2026).fit_predict(z)
        result=cluster_sensitivity(frame,labels,3,3)
        self.assertEqual(result.loc[result.escenario.eq('referencia'),'ari_referencia'].iloc[0],1.)


if __name__=='__main__': unittest.main()
