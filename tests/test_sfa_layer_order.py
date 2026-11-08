"""레이어 번호=아래→위 순서 맞춤 검사(합성). 앱 실제 표시 확인이 아니다."""
import sys,unittest
from pathlib import Path
import xml.etree.ElementTree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import sfa_layer_order as LO


def seq():
    root=E.Element('Sequence')
    for names in ((('2','outline_glow'),('0','Layer 1'),('1','smear')),(('2','outline_glow'),('0','Layer 1')),(('2','outline_glow'),('0','Layer 1'),('1','smear_review'))):
        f=E.SubElement(root,'Frame')
        for i,n in names:E.SubElement(f,'LayerDef',ID=i,Name=n)
        for i,_ in names:E.SubElement(f,'AO',ID=f'9{i}',TypeId='1',LayerId=i)
    return root


class LayerOrder(unittest.TestCase):
    def test_outline_written_first_becomes_lowest_number(self):
        r=seq();self.assertFalse(LO.check(r)['order_matches_ids'])
        m=LO.renumber_bottom_to_top(r);self.assertEqual(m,{'2':'0','0':'1','1':'2'})
        c=LO.check(r);self.assertTrue(c['order_matches_ids']);self.assertEqual(c['layer_ids_with_multiple_names'],0)
        f=r.findall('Frame')[0];self.assertEqual([a.get('LayerId') for a in f.findall('AO')],['0','1','2'])
        self.assertEqual({l.get('Name') for fr in r.findall('Frame') for l in fr.findall('LayerDef') if l.get('ID')=='2'},{'smear'})

    def test_conflicting_order_is_rejected(self):
        r=seq();f=r.findall('Frame')[1]
        for l in f.findall('LayerDef'):f.remove(l)
        E.SubElement(f,'LayerDef',ID='0');E.SubElement(f,'LayerDef',ID='2')
        with self.assertRaises(ValueError):LO.renumber_bottom_to_top(r)


if __name__=='__main__':
    unittest.main()
