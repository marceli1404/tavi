"""Browser fixture evaluation can only run generated local content."""
import io
import json
import unittest
from unittest.mock import Mock, patch

from tavi_browser_eval import _verified_fixture_click, run_fixture_suite, main
from tavi_metrics import UsageMetrics


class EvalSafetyTests(unittest.TestCase):
    def test_rejects_external_page_or_unauthorized_route_without_action(self):
        page=Mock()
        page.url='https://outside.example'
        page.locator.return_value.count.return_value=0
        metrics=UsageMetrics()
        self.assertFalse(_verified_fixture_click(page,
                        dict(route='host_control',control={'candidate':{'id':'x'}}),
                        metrics))
        page.get_by_role.assert_not_called()
        self.assertFalse(_verified_fixture_click(page,
                        dict(route='host_review'),metrics))
        page.get_by_role.assert_not_called()

    def test_repeats_bound_before_playwright_import(self):
        for value in (0,26,True,-1,'4',None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                run_fixture_suite(repeats=value)

    def test_cli_does_not_accept_websites_or_paths_to_pages(self):
        for args in (['--url','https://example.com'],['--page','x.html'],
                     ['--executable','/usr/bin/chrome']):
            with self.subTest(args=args),patch('sys.stderr',new_callable=io.StringIO),self.assertRaises(SystemExit) as ctx:
                main(args)
            self.assertEqual(ctx.exception.code,2)

    def test_fixture_benchmark_uses_no_prompts_or_host_model(self):
        from tavi_browser_eval import _SIMPLE, _DISABLED, _AMBIGUOUS, _MISSING
        for content in (_SIMPLE,_DISABLED,_AMBIGUOUS,_MISSING):
            self.assertIn('data-tavi-fixture="v1"',content)
            self.assertNotIn('https://',content)
            self.assertNotIn('http://',content)
            self.assertNotIn('<script src=',content)


if __name__=='__main__':
    unittest.main()
