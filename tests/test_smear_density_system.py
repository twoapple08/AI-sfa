import copy,json,sys,tempfile,unittest,zipfile
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import smear_density as S

class DensitySystemTests(unittest.TestCase):
    def setUp(self):
        self.profile=json.loads(S.DEFAULT_PROFILE.read_text())
        self.points=[[100,100],[100,140],[102,100],[102,140],[118,100],[118,140],[120,100]]
        self.doc=dict(schema='sfa-smear-density-input/1',canvas=[852,480],cases=[dict(id='probe',points_px=self.points)])

    def test_reference_mode_uses_original_gap_independent_of_added_count(self):
        p=json.loads((S.ROOT/'profiles/smear_density_v1_1_reference.json').read_text())
        points=[[0,0],[0,80],[4.8,0],[4.8,80],[9.6,0]]
        a=S.process(points,[852,480],p)
        p['max_gap']=.8;p['min_gap']=.4
        b=S.process(points,[852,480],p)
        self.assertGreater(b['added_pairs'],a['added_pairs'])
        for result in [a,b]:
            for interval in result['intervals']:
                for bounds in interval['effective_depth_bounds']:
                    np.testing.assert_allclose(bounds,[.12,.26])

    def test_reference_mode_half_original_gap_halves_depth_range(self):
        p=json.loads((S.ROOT/'profiles/smear_density_v1_1_reference.json').read_text())
        p['max_gap']=1.2;p['min_gap']=.6
        r=S.process([[0,0],[0,80],[2.4,0],[2.4,80],[4.8,0]],[852,480],p)
        self.assertGreater(r['added_pairs'],0)
        for interval in r['intervals']:
            for bounds in interval['effective_depth_bounds']:
                np.testing.assert_allclose(bounds,[.06,.13])
        doubled=S.process(np.array(r['base_points_px'])*2,[1704,960],p)
        np.testing.assert_allclose(np.array(r['points_px'])*2,doubled['points_px'])

    def test_geometry_fixes_original_and_depths_are_bounded(self):
        r=S.process(self.points,[852,480],self.profile)
        np.testing.assert_array_equal(np.array(r['points_px'])[r['fixed_mask']],self.points)
        self.assertEqual(r['segments']%2,0);self.assertGreater(r['added_pairs'],0)
        ds=[d for x in r['intervals'] for pair in x['depth_pairs'] for d in pair]
        self.assertTrue(all(0<=d<=.26 for d in ds))
        self.assertTrue(any(d<.12 for d in ds))
        for interval in r['intervals']:
            for scale,bounds,pair in zip(interval['depth_scales'],interval['effective_depth_bounds'],interval['depth_pairs']):
                np.testing.assert_allclose(bounds,np.array([.12,.26])*scale)
                self.assertTrue(all(bounds[0]<=d<=bounds[1] for d in pair))

    def test_uniform_resize_keeps_counts_and_normalized_shape(self):
        a=S.process(self.points,[852,480],self.profile)
        b=S.process(np.array(self.points)*2,[1704,960],self.profile)
        self.assertEqual(a['segments'],b['segments'])
        np.testing.assert_allclose(np.array(a['points_px'])*2,b['points_px'])

    def test_already_dense_case_does_not_change(self):
        p=[[0,0],[0,100],[1,0],[1,100],[2,0]]
        r=S.process(p,[852,480],self.profile)
        self.assertEqual(r['added_pairs'],0);np.testing.assert_array_equal(r['points_px'],p)

    def test_sfa_integrity_and_mutation_is_detected(self):
        r=S.process(self.points,[852,480],self.profile);root=S.export_sfa(r,[852,480],self.profile)
        self.assertEqual(S.inspect_sfa(root,r,[852,480],self.profile)['unique_points'],2*r['segments'])
        root.find('.//AO').set('Color','0')
        with self.assertRaises(ValueError):S.inspect_sfa(root,r,[852,480],self.profile)

    def test_deterministic_files_and_fresh_ids_between_cases(self):
        self.doc['cases'].append(dict(id='second',points_px=(np.array(self.points)+[40,0]).tolist()))
        with tempfile.TemporaryDirectory() as d:
            a=S.run(self.doc,self.profile,Path(d)/'a');b=S.run(self.doc,self.profile,Path(d)/'b')
            self.assertEqual([c['sha256'] for c in a['cases']],[c['sha256'] for c in b['cases']])
            import xml.etree.ElementTree as E
            seen=set()
            for c in a['cases']:
                with zipfile.ZipFile(Path(d)/'a'/c['file']) as z:root=E.fromstring(z.read('review.xml'))
                ids={p.get('ID') for p in root.findall('.//AP')}
                self.assertFalse(seen&ids);seen|=ids

    def test_partial_failure_is_explicit_and_has_no_sfa(self):
        self.doc['cases'].append(dict(id='bad',points_px=[[0,0]]))
        with tempfile.TemporaryDirectory() as d:
            r=S.run(self.doc,self.profile,d)
            self.assertEqual([c['status'] for c in r['cases']],['ok','needs_review'])
            self.assertFalse((Path(d)/'bad.sfa').exists())

    def test_wrong_profile_and_path_ids_are_rejected(self):
        p=copy.deepcopy(self.profile);p['depths']=[.3]
        with self.assertRaises(ValueError):S.validate_profile(p)
        self.doc['cases'][0]['id']='../escape'
        with tempfile.TemporaryDirectory() as d,self.assertRaises(ValueError):S.run(self.doc,self.profile,d)

    def test_existing_outputs_and_result_reinput_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r=S.run(self.doc,self.profile,d)
            with self.assertRaises(ValueError):S.run(self.doc,self.profile,d)
        with tempfile.TemporaryDirectory() as d,self.assertRaises(ValueError):S.run(r,self.profile,d)

    def test_template_rails_are_supported(self):
        doc=copy.deepcopy(self.doc);doc['cases']=[dict(id='rails',template_points_px=[[0,0],[0,10],[10,0],[10,10],[20,0]],rail_a=[[100,100],[120,100]],rail_b=[[100,140],[120,140]],segments=4)]
        with tempfile.TemporaryDirectory() as d:
            r=S.run(doc,self.profile,d)
            self.assertEqual(r['cases'][0]['status'],'ok')

    def test_close_turns_reduce_min_max_and_width_together(self):
        p=np.array([[0,0],[0,20],[3,0],[3,20],[6,0],[6,20],[9,0]],float)
        fixed=np.array([True,True,False,False,True,True,True])
        scales,gaps=S.depth_spacing_scales(p,fixed,6)
        self.assertEqual(gaps,[3.]);self.assertEqual(scales,[.5])
        np.testing.assert_allclose(np.array([.12,.26])*scales[0],[.06,.13])
        wide=p.copy();wide[:,0]*=4
        self.assertEqual(S.depth_spacing_scales(wide,fixed,6)[0],[1.])

    def test_cli_runs_and_returns_nonzero_for_review_cases(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.json';p.write_text(json.dumps(self.doc))
            command=[sys.executable,str(S.ROOT/'tools/smear_density.py'),'--input',str(p),'--output',str(Path(d)/'ok')]
            self.assertEqual(subprocess.run(command,capture_output=True).returncode,0)
            self.doc['cases'][0]['points_px']=[[0,0]];p.write_text(json.dumps(self.doc))
            command[-1]=str(Path(d)/'bad')
            self.assertEqual(subprocess.run(command,capture_output=True).returncode,2)
