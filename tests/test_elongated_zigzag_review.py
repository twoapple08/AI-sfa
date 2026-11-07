import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import elongated_zigzag_review as E
import zigzag_smear_review as Z

class ElongatedStrokeTests(unittest.TestCase):
    def test_longer_returns_keep_attachment_and_transverse_width(self):
        near=np.array([20.,20.]);far=np.array([20.,120.])
        old=Z.zigzag(near,far,0,20,38);new=E.elongate(old,near,far,attached=True)
        np.testing.assert_allclose(new[0],near)
        np.testing.assert_allclose(new[:,0],old[:,0])
        self.assertEqual(new.shape,old.shape)
        self.assertGreater(np.linalg.norm(np.diff(new,axis=0),axis=1).mean(),np.linalg.norm(np.diff(old,axis=0),axis=1).mean())
