from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import sfa_tokens as K
import seq_train as T
from seq_objective import objective, metadata
from seq_refine import load_plan, prepare
from seq_target_audit import audit_npz, audit_folder
from kaggle_seq_refinement import prepare_kernel
import numpy as np


def target(objects=1):
    root = ET.Element('Sequence', HeightWidthRatio='0.5625', BackgroundColor='-16777216')
    frame = ET.SubElement(root, 'Frame', Position='0', BackgroundColor='-16777216')
    ET.SubElement(frame, 'LayerDef', ID='0', Name='시험', Visible='true', Locked='false')
    for i in range(objects):
        obj = ET.SubElement(frame, 'AO', ID=str(i+1), TypeId='3', Color='-1', LayerId='0', DrawOrder=str(i+1),
                            ThicknessScale='1', GlowRadius='10', GlowThickness='20', GlowColor='4294901760', GlowAlpha='128')
        for k, (x, y) in enumerate([(10+i*5, 20), (40+i*5, 80), (70+i*5, 20)]):
            ET.SubElement(obj, 'AP', ID=str(i*3+k+1), Index=str(k), Flags='4', X=str(x), Y=str(y))
    fill = ET.SubElement(frame, 'FR', Color='2164195328')
    ET.SubElement(fill, 'FS', ObjId=str(objects), StartT='0', EndT='1', Contour='0')
    return K.encode(root, frame)[0]


def tensors(tokens, padding=0):
    tgt = torch.tensor([tokens[1:]+[K.TOK['PAD']]*padding])
    fld = torch.tensor([K.fields(tokens)[1:]+[0]*padding])
    return tgt, fld


class TestSeqObjective(unittest.TestCase):
    def test_legacy_is_exactly_preserved_and_padding_is_ignored(self):
        tokens = target()
        tgt, fld = tensors(tokens)
        logits = torch.randn(1, tgt.shape[1], K.VOCAB, generator=torch.Generator().manual_seed(5))
        old = T.loss_fn(logits, tgt, fld)[0]
        new, _ = objective(logits, tgt, fld, [tokens], 'token-v1')
        self.assertTrue(torch.equal(old, new))
        a, parts_a = objective(logits, tgt, fld, [tokens])
        padded, padded_fld = tensors(tokens, 5)
        b, parts_b = objective(torch.cat([logits, torch.zeros(1, 5, K.VOCAB)], 1), padded, padded_fld, [tokens])
        torch.testing.assert_close(a, b)
        for key in parts_a:
            torch.testing.assert_close(parts_a[key], parts_b[key])

    def test_stop_strengthens_finish_and_continuation_at_their_legal_positions(self):
        tokens = target()
        tgt, fld = tensors(tokens)
        record = metadata(tuple(tokens))
        negative = next(p for p, *_, label in record[0] if not label)
        logits = torch.zeros(1, tgt.shape[1], K.VOCAB, requires_grad=True)
        with torch.no_grad():
            logits[0, negative, K.TOK['EOS']] = 10
        old = T.loss_fn(logits, tgt, fld)[0]
        new, _ = objective(logits, tgt, fld, [tokens])
        a = torch.autograd.grad(old, logits, retain_graph=True)[0]
        b = torch.autograd.grad(new, logits)[0]
        end = len(tokens)-2
        self.assertLess(float(b[0, end, K.TOK['EOS']]), float(a[0, end, K.TOK['EOS']]))
        self.assertGreater(float(b[0, negative, K.TOK['EOS']]), float(a[0, negative, K.TOK['EOS']]))

    def test_stop_does_not_learn_from_illegal_eos_positions(self):
        tokens = target()
        tgt, fld = tensors(tokens)
        logits = torch.zeros(1, tgt.shape[1], K.VOCAB, requires_grad=True)
        _, parts = objective(logits, tgt, fld, [tokens])
        grad = torch.autograd.grad(parts['stop'], logits)[0]
        allowed = {p for p, *_ in metadata(tuple(tokens))[0]}
        for p in range(tgt.shape[1]):
            if p not in allowed:
                self.assertEqual(float(grad[0, p].abs().max()), 0.)

    def test_positive_stop_gradient_is_not_diluted_by_object_count(self):
        gradients = []
        for n in (1, 3):
            tokens = target(n)
            tgt, fld = tensors(tokens)
            logits = torch.zeros(1, tgt.shape[1], K.VOCAB, requires_grad=True)
            _, parts = objective(logits, tgt, fld, [tokens])
            gradients.append(torch.autograd.grad(parts['stop'], logits)[0][0, -1, K.TOK['EOS']])
        torch.testing.assert_close(*gradients)

    def test_background_glow_fill_and_first_object_are_included(self):
        tokens = target()
        tgt, fld = tensors(tokens)
        logits = torch.zeros(1, tgt.shape[1], K.VOCAB, requires_grad=True)
        _, parts = objective(logits, tgt, fld, [tokens])
        first = torch.autograd.grad(parts['first_object'], logits, retain_graph=True)[0]
        appearance = torch.autograd.grad(parts['appearance'], logits)[0]
        lo, hi = metadata(tuple(tokens))[1]
        self.assertEqual(float(first[0, :lo].abs().sum()), 0.)
        self.assertEqual(float(first[0, hi:].abs().sum()), 0.)
        for name in ('bg', 'glow', 'obj'):
            self.assertGreater(float(appearance[0, fld[0] == K.FID[name]].abs().sum()), 0.)

    def test_bad_end_or_field_alignment_is_rejected(self):
        tokens = target()
        for bad in (tokens[:-1], tokens+[K.TOK['EOS']]):
            with self.assertRaises(ValueError):
                metadata(tuple(bad))
        tgt, fld = tensors(tokens)
        fld[0, 0] = K.FID['glow']
        with self.assertRaisesRegex(ValueError, '칸 번호'):
            objective(torch.zeros(1, tgt.shape[1], K.VOCAB), tgt, fld, [tokens])

    def test_cpu_preparation_does_not_train_or_overwrite_parent(self):
        profile = Path(__file__).resolve().parents[1]/'profiles/seq_refinement_balanced_v1.json'
        self.assertEqual(load_plan(profile)['steps_per_arm'], 500)
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)/'parent.pt'
            torch.save(dict(cfg={'maxlen': 2048}, step=12, model={}), parent)
            original = parent.read_bytes()
            out = Path(temp)/'experiment'
            result = prepare(parent, '자료', '검증', out, profile)
            self.assertFalse(result['official'])
            self.assertEqual(parent.read_bytes(), original)
            self.assertEqual(list(out.glob('*.pt')), [])
            with self.assertRaises(ValueError):
                prepare(parent, '자료', '검증', out, profile)

    def test_actual_problem_npz_audit_preserves_all_features(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'problem.npz'
            a, b = target(1), target(3)
            np.savez(path, tok=np.array(a+b), off=np.array([0, len(a), len(a)+len(b)]))
            report = audit_npz(path)
            self.assertEqual(report['sequences'], 2)
            self.assertEqual(report['eos_positive'], 2)
            for kind in ('curve', 'fill', 'glow', 'nonwhite_background'):
                self.assertEqual(report['feature_counts'][kind], 2)
            self.assertEqual(audit_folder(temp)['sequences'], 2)

    def test_kaggle_preparation_is_private_pinned_and_separate_from_official_training(self):
        with tempfile.TemporaryDirectory() as temp:
            meta = prepare_kernel(temp, '1'*40, '2'*64, '3'*40, 'test-account')
            self.assertTrue(meta['is_private'])
            self.assertIn('refine-ab', meta['id'])
            self.assertNotEqual(meta['id'], 'test-account/aisfa-seq-train')
            source = (Path(temp)/'kernel.py').read_text()
            self.assertIn("'branch': 'claude/new-session-gknz4t'", source)
            self.assertIn("'official': False", source)
            compile(source, 'kernel.py', 'exec')


if __name__ == '__main__':
    unittest.main()
