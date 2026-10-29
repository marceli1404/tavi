import copy
import hashlib,json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from tavi_model import DecisionModel,coding_document

BASE=Path(__file__).parent/'models/tavi-v4-clean'

class DocRoutingTests(unittest.TestCase):
    def setUp(self):
        self.base=DecisionModel.load(BASE)
        self.meta=copy.deepcopy(self.base.metadata);self.arrays={k:v.copy() for k,v in self.base.arrays.items()}
        self.meta['coding_doc_adapter']=dict(vocabulary={'w:return':0},width=2,minimum_confidence=.5,architecture='docstring_tfidf_mlp')
        self.arrays.update(coding_doc_idf=np.ones(1,dtype='float32'),coding_doc_W=np.zeros((1,2),dtype='float32'),
                           coding_doc_b=np.zeros(2,dtype='float32'),coding_doc_V=np.zeros((2,4),dtype='float32'),coding_doc_c=np.array([10.,-10.,-10.,-10.],dtype='float32'))

    def candidate(self):return DecisionModel(self.meta,self.arrays)

    def test_plain_text_and_skill_external_outputs_remain_identical(self):
        tasks=['Fix a mobile menu','Audit an authentication service','Say hello','Help me with the thing']
        for a,b in zip(self.base.predict(tasks),self.candidate().predict(tasks)):np.testing.assert_array_equal(a,b)

    def test_document_head_applies_only_to_explicit_coding_specs(self):
        task='def routine(values):\n    """Return an integer."""'
        self.assertEqual(self.candidate().infer(task)['tier'],'fast')
        self.assertEqual(coding_document(task),'Return an integer.')
        a,b=self.base.predict([task]),self.candidate().predict([task])
        np.testing.assert_array_equal(a[1],b[1]);np.testing.assert_array_equal(a[2],b[2])

    def test_uncertain_document_output_preserves_existing_code_route(self):
        self.arrays['coding_doc_c'][:]=0
        task='def routine(values):\n    """Return the total of the readings."""'
        np.testing.assert_array_equal(self.base.predict([task])[0],self.candidate().predict([task])[0])

    def test_document_review_does_not_erase_existing_route(self):
        self.arrays['coding_doc_c'][:]=[-10.,-10.,-10.,10.]
        task='def routine(values):\n    """Return the total of the readings."""'
        self.assertNotEqual(self.base.infer(task)['tier'],'review')
        np.testing.assert_array_equal(self.base.predict([task])[0],self.candidate().predict([task])[0])

    def test_loading_rejects_malformed_document_head(self):
        for change in ('shape','threshold','vocabulary'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as tmp:
                meta=copy.deepcopy(self.meta);arrays={k:v.copy() for k,v in self.arrays.items()}
                if change=='shape':arrays['coding_doc_V']=np.zeros((3,4))
                if change=='threshold':meta['coding_doc_adapter']['minimum_confidence']=True
                if change=='vocabulary':meta['coding_doc_adapter']['vocabulary']={'w:return':2}
                path=Path(tmp);np.savez_compressed(path/'weights.npz',**arrays)
                meta['weights_sha256']=hashlib.sha256((path/'weights.npz').read_bytes()).hexdigest();(path/'model.json').write_text(json.dumps(meta))
                with self.assertRaisesRegex(ValueError,'document adapter'):DecisionModel.load(path)

    def test_presence_gate_suppresses_optional_scores_without_altering_tiers(self):
        self.meta['skill_presence']=dict(vocabulary={'w:hello':0},threshold=.5)
        self.arrays.update(skill_presence_idf=np.ones(1),skill_presence_W=np.zeros(1),skill_presence_b=np.array(-30.))
        task='Fix a mobile navigation menu'
        before=self.base.predict([task]);after=self.candidate().predict([task])
        np.testing.assert_array_equal(before[0],after[0]);np.testing.assert_array_equal(before[2],after[2])
        self.assertTrue(np.all(after[1]==0))

    def test_explicit_skill_survives_a_negative_presence_gate(self):
        from tavi_router import route_custom
        self.meta['skill_presence']=dict(vocabulary={'w:hello':0},threshold=.5)
        self.arrays.update(skill_presence_idf=np.ones(1),skill_presence_W=np.zeros(1),skill_presence_b=np.array(-30.))
        skill=dict(id='responsive',name='responsive-design',description='Responsive layout',path='skill.md')
        catalog=[dict(id='gpt-6.1-sol',default_effort='medium',efforts=['low','medium','high'])]
        result=route_custom('Fix a mobile menu',[skill],catalog,self.candidate(),requested_skills=['responsive-design'])
        self.assertEqual(result['skills'][0]['name'],'responsive-design')
        self.assertEqual(result['skills'][0]['selection'],'explicit')

    def test_review_expert_can_request_review_for_an_underspecified_contract(self):
        self.meta['coding_doc_adapter']['review_gate']=dict(threshold=.5)
        self.arrays.update(coding_doc_review_W=np.zeros(1),coding_doc_review_b=np.array(30.))
        self.arrays['coding_doc_c'][:]=[-10.,-10.,-10.,10.]
        self.assertEqual(self.candidate().infer('def routine(values):\n    """Implement the unspecified rule."""')['tier'],'review')

    def test_rejected_research_gate_prevents_activation_even_if_core_test_passed(self):
        import shutil
        from tavi_health import activate_candidate
        from tavi_probability import signature
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);candidate=root/'candidate';candidate.mkdir()
            for name in ('weights.npz','model.json'):shutil.copyfile(BASE/name,candidate/name)
            metadata=json.loads((candidate/'model.json').read_text())
            (candidate/'activation-gate.json').write_text(json.dumps(dict(format='tavi-acceptance-v1',approved=False,
                weights_sha256=metadata['weights_sha256'],model_signature=signature(metadata))))
            config=root/'config.json';before=b'{"model_path":"previous"}';config.write_bytes(before)
            with self.assertRaisesRegex(ValueError,'acceptance gate'):
                activate_candidate(config,before,candidate,dict(passed=True,weights_sha256=metadata['weights_sha256'],model_signature=signature(metadata)))
            self.assertEqual(config.read_bytes(),before)
            self.assertFalse((candidate/'previous-config.json').exists())

if __name__=='__main__':unittest.main()
