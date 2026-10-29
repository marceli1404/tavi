import json
from pathlib import Path
import shutil
import tempfile
import unittest
from tavi_target import DEFAULT,load


class FieldAuditTests(unittest.TestCase):
    def test_current_model_reports_failure_and_does_not_qualify_actions(self):
        metadata,_=load()
        self.assertFalse(metadata['automatic_probability_qualified'])
        self.assertEqual(metadata['field_evaluation']['status'],'failed')
        self.assertEqual(metadata['field_evaluation']['check']['high95_correct'],0)

    def test_audit_cannot_be_reused_for_other_weights_or_claim_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'model'; shutil.copytree(DEFAULT,root)
            path=root/'field-evaluation.json'; original=json.loads(path.read_text())
            for key,value in (('weights_sha256','0'*64),('automatic_probability_qualified',True),('status','passed')):
                audit={**original,key:value}; path.write_text(json.dumps(audit))
                with self.assertRaises(ValueError): load(root)

    def test_missing_audit_does_not_restore_automatic_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'model'; root.mkdir()
            for name in ('weights.npz','model.json'): shutil.copyfile(DEFAULT/name,root/name)
            metadata,_=load(root)
            self.assertFalse(metadata['automatic_probability_qualified'])


if __name__=='__main__': unittest.main()
