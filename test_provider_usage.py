"""Provider token adapter: only official response usage metadata may count."""
import unittest
from tavi_metrics import UsageMetrics
from tavi_provider_usage import extract,record


class ProviderUsageTests(unittest.TestCase):
    def test_responses_api_total_and_cache_are_reported(self):
        raw=dict(id='example',output=[dict(text='PRIVATE RESPONSE')],
                 usage=dict(input_tokens=210,output_tokens=39,total_tokens=249,
                            input_tokens_details=dict(cached_tokens=100)))
        m=UsageMetrics()
        self.assertTrue(record(m,'openai_responses',raw,elapsed_ms=130))
        result=m.summary()
        self.assertEqual(result['provider_tokens']['input'],210)
        self.assertEqual(result['provider_tokens']['output'],39)
        self.assertEqual(result['provider_tokens']['cached_input'],100)
        self.assertNotIn('PRIVATE RESPONSE',str(result))

    def test_chat_completions_and_sdk_dict_wrapper(self):
        class SDK:
            def model_dump(self,**kwargs):
                return dict(usage=dict(prompt_tokens=60,completion_tokens=20,
                    total_tokens=80,prompt_tokens_details=dict(cached_tokens=0)),
                    choices=[dict(message={'content':'DO NOT SAVE'})])
        m=UsageMetrics()
        self.assertTrue(record(m,'openai_chat_completions',SDK()))
        self.assertEqual(m.summary()['provider_tokens']['cached_input'],0)
        self.assertEqual(m.summary()['provider_tokens']['cached_input_status'],'reported')
        self.assertNotIn('DO NOT SAVE',str(m.summary()))

    def test_missing_provider_usage_stays_unknown(self):
        m=UsageMetrics()
        self.assertFalse(record(m,'openai_responses',dict(output=[{'text':'secret'}])))
        self.assertEqual(m.summary()['provider_tokens']['status'],'unavailable')
        self.assertIsNone(m.summary()['provider_tokens']['input'])
        self.assertIsNone(m.summary()['provider_tokens']['cached_input'])
        self.assertEqual(m.summary()['provider_tokens']['unmeasured_calls'],1)

    def test_missing_cached_metadata_stays_unknown(self):
        m=UsageMetrics()
        record(m,'openai_responses',dict(usage=dict(input_tokens=10,output_tokens=2)))
        result=m.summary()['provider_tokens']
        self.assertEqual(result['status'],'reported')
        self.assertIsNone(result['cached_input'])
        self.assertEqual(result['cached_input_status'],'unavailable')
        record(m,'openai_responses',dict(usage=dict(input_tokens=11,output_tokens=3,
                                                 input_tokens_details=dict(cached_tokens=1))))
        self.assertIsNone(m.summary()['provider_tokens']['cached_input'])
        self.assertEqual(m.summary()['provider_tokens']['cached_input_status'],'partial')

    def test_invalid_usage_is_not_accounted(self):
        m=UsageMetrics()
        bad=[
            dict(input_tokens=2,output_tokens=-1),
            dict(input_tokens=True,output_tokens=2),
            dict(input_tokens=2,output_tokens=3,total_tokens=99),
            dict(input_tokens=4,output_tokens=None),
            dict(input_tokens=10,output_tokens=2,input_tokens_details=dict(cached_tokens=11)),
        ]
        for usage in bad:
            with self.subTest(usage=usage),self.assertRaises(ValueError):
                record(m,'openai_responses',dict(usage=usage))
        self.assertEqual(m.summary()['provider_tokens']['calls'],0)
        with self.assertRaises(ValueError):
            extract('unknown',{})


if __name__=='__main__':unittest.main()
