"""Read-only browser control snapshot compatibility and provenance tests."""
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from tavi_browser_snapshot import _DOM_SCRIPT, capture_controls
from tavi_observe import dispatch


def item(**updates):
    result=dict(id='dom-0-settings',label='Settings',role='button',
                context='Toolbar',visible=True,enabled=True,
                bounds=[10,10,120,32])
    result.update(updates)
    return result


class FakePage:
    def __init__(self, records=None):
        self.records = records if records is not None else [item()]
        self.evaluate = Mock(side_effect=self.read)

    def read(self,script):
        if script!=_DOM_SCRIPT:
            raise AssertionError('Unexpected page evaluation')
        return {'viewport':[1280,720],'controls':self.records}


class BrowserSnapshotTests(unittest.TestCase):
    def test_live_page_adapter_creates_valid_host_timed_control_inventory(self):
        page=FakePage([item()])
        before=datetime.now(timezone.utc)
        snapshot=capture_controls(page)
        after=datetime.now(timezone.utc)
        self.assertEqual(page.evaluate.call_count,1)
        self.assertEqual(snapshot['source'],'supported_browser_dom')
        self.assertEqual(snapshot['controls'],[item()])
        self.assertTrue(before<=datetime.fromisoformat(snapshot['captured_at'])<=after)
        self.assertNotIn('url',snapshot)
        q=[dict(task='Find Settings',target='Settings',role='button',context='Toolbar')]
        result=dispatch(snapshot,q)
        self.assertEqual(result['routes'][0]['route'],'host_control')
        self.assertEqual(result['counts']['image_preparations'],0)
        self.assertFalse(result['executed_actions'])

    def test_each_snapshot_has_fresh_host_generated_identity(self):
        page=FakePage()
        first=capture_controls(page)
        second=capture_controls(page)
        self.assertNotEqual(first['snapshot_id'],second['snapshot_id'])
        self.assertNotEqual(first['captured_at'],'')
        self.assertEqual(first['source'],'supported_browser_dom')

    def test_browser_control_fields_are_rejected_if_invalid(self):
        invalid=[
            [item(bounds=[-1,float('nan'),30,20])],
            [item(visible='yes')],
            [item(role='secret')],
            [item(id='duplicate'), item(id='duplicate',label='Other')],
            [item(label='')],
        ]
        for records in invalid:
            with self.subTest(records=str(records)[:80]), self.assertRaises(ValueError):
                capture_controls(FakePage(records))

    def test_bounds_and_roles_cover_native_aria_button_link_and_inputs(self):
        page=FakePage([
            item(id='dom-0-submit',label='Submit',role='button'),
            item(id='dom-1-about',label='About',role='link'),
            item(id='dom-2-search',label='Search',role='textbox'),
            item(id='dom-3-privacy',label='Privacy',role='checkbox')])
        snapshot=capture_controls(page)
        qs=[dict(task='Inspect '+x,target=x,role=role) for x,role in
            [('Submit','button'),('About','link'),('Search','textbox'),('Privacy','checkbox')]]
        result=dispatch(snapshot,qs)
        self.assertEqual(result['counts']['exact_host_controls'],4)
        self.assertEqual(result['counts']['ocr_passes'],0)

    def test_javascript_only_reads_dom_and_never_touches_sensitive_value_or_click(self):
        self.assertIn('getBoundingClientRect',_DOM_SCRIPT)
        self.assertIn('aria-labelledby',_DOM_SCRIPT)
        self.assertIn('aria-disabled',_DOM_SCRIPT)
        self.assertIn('getComputedStyle',_DOM_SCRIPT)
        self.assertIn('getAttribute',_DOM_SCRIPT)
        for forbidden in ('.click(', '.value', 'localStorage', 'document.cookie',
                          'fetch(', 'XMLHttpRequest', 'screenshot('):
            self.assertNotIn(forbidden,_DOM_SCRIPT)

    def test_invalid_page_payload_fails_closed(self):
        page=FakePage()
        page.evaluate=Mock(return_value={'viewport':[100,200]})
        with self.assertRaisesRegex(ValueError,'Invalid browser control'):
            capture_controls(page)
        for value in (12,'', 'x'*201):
            with self.assertRaises(ValueError):
                capture_controls(page,snapshot_id=value)


if __name__=='__main__':
    unittest.main()
