import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

import app
from tests import test_moments_v2 as legacy


class MomentVisibilityTests(unittest.TestCase):
    setUp = legacy.MomentEditingTests.setUp
    tearDown = legacy.MomentEditingTests.tearDown
    _insert_photo = legacy.MomentEditingTests._insert_photo
    make_moment = legacy.MomentEditingTests.make_moment

    def test_hide_rescan_restore_preserves_memory_and_excludes_deleted(self):
        row = self.make_moment()
        url = f"/api/moments/{row['id']}"
        self.assertEqual(self.client.post(url + '/hide').status_code, 200)
        self.assertEqual(self.client.post(url + '/hide').status_code, 200)
        app._detect_moment_candidates()
        data = self.client.get('/api/moments').json
        self.assertEqual(data['suggested'], [])
        self.assertEqual([m['id'] for m in data['hidden']], [row['id']])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url + '/restore').status_code, 200)
        data = self.client.get('/api/moments').json
        self.assertEqual(data['hidden'], [])
        self.assertEqual([m['id'] for m in data['suggested']], [row['id']])
        with app.closing(app.get_conn()) as conn:
            restored = conn.execute('SELECT * FROM moments WHERE id=?', (row['id'],)).fetchone()
        for key in ('title', 'photo_ids_json', 'script_json', 'user_edited'):
            self.assertEqual(restored[key], row[key])
        self.assertEqual(restored['revision'], row['revision'] + 2)
        self.client.delete(url)
        self.assertEqual(self.client.get('/api/moments').json['hidden'], [])
        self.assertEqual(self.client.post(url + '/restore').status_code, 404)

    def test_viewer_cannot_list_hide_or_restore_hidden_memories(self):
        row = self.make_moment()
        url = f"/api/moments/{row['id']}"
        self.client.post(url + '/hide')
        with self.client.session_transaction() as session:
            session['_user_id'] = '2'
        self.assertEqual(self.client.get('/api/moments').json['hidden'], [])
        self.assertEqual(self.client.post(url + '/hide').status_code, 403)
        self.assertEqual(self.client.post(url + '/restore').status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_unknown_and_saved_memories_are_not_changed(self):
        self.assertEqual(self.client.post('/api/moments/999/hide').status_code, 404)
        row = self.make_moment()
        url = f"/api/moments/{row['id']}"
        self.client.post(url + '/accept')
        self.assertEqual(self.client.post(url + '/hide').status_code, 404)
        self.assertEqual(self.client.post(url + '/restore').status_code, 404)
        self.assertEqual(len(self.client.get('/api/moments').json['saved']), 1)

    def test_browser_hide_and_restore_desktop_and_mobile(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest('Playwright unavailable')
        self.make_moment()
        source = (Path(__file__).resolve().parents[1] / 'static/app.js').read_text(encoding='utf-8')
        functions = source[source.index('function _momentCardHtml('):source.index('async function startMomentDetection(')]
        functions += source[source.index('async function dismissMoment('):source.index('async function deleteMoment(')]
        labels = dict(momenter_hidden='Skjulte minder', momenter_back='Tilbage til minder',
                      momenter_restore='Vis igen', momenter_dismiss='Skjul',
                      momenter_hidden_empty='Ingen skjulte minder.')
        harness = '''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
        <link rel="stylesheet" href="/static/styles.css"><main id="grid"></main><p id="status"></p>
        <script>const state={currentUser:{role:'admin'},view:'momenter'};
        const els={grid:document.getElementById('grid')};
        function escapeHtml(s){const e=document.createElement('span');e.textContent=String(s);return e.innerHTML.replaceAll('"','&quot;')}
        function tr(s){return LABELS[s] || s}
        function _momentDateRangeLabel(m){return m.start_date}
        function momentEvidenceHtml(){return ''}
        function editMomentHome(){} function startMomentDetection(){}
        function showStatus(s){document.getElementById('status').textContent=s}
        function renderGrid(){renderMomentsPanel()}
        FUNCTIONS
        loadMoments();</script>'''.replace('LABELS', json.dumps(labels)).replace('FUNCTIONS', functions)
        errors = []
        with sync_playwright() as runtime:
            try:
                browser = runtime.chromium.launch(headless=True)
            except Exception as exc:
                self.skipTest(f'Chromium unavailable: {exc}')
            page = browser.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))

            def route(request_route):
                request = request_route.request
                path = urlsplit(request.url).path
                if path == '/':
                    request_route.fulfill(body=harness, content_type='text/html')
                    return
                response = self.client.open(path, method=request.method)
                request_route.fulfill(status=response.status_code, body=response.get_data(), content_type=response.content_type)
                response.close()

            page.route('**/*', route)
            for width in (1440, 390):
                page.set_viewport_size(dict(width=width, height=900))
                page.goto('http://fjordlens.test/')
                page.get_by_role('button', name='Skjul', exact=True).click()
                page.get_by_role('button', name='Skjulte minder (1)', exact=True).click()
                page.get_by_role('button', name='Vis igen', exact=True).wait_for()
                self.assertEqual(page.locator('[data-moment-action="dismiss"]').count(), 0)
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
                page.get_by_role('button', name='Vis igen', exact=True).click()
                page.get_by_text('Ingen skjulte minder.', exact=True).wait_for()
                page.get_by_role('button', name='Tilbage til minder', exact=True).click()
                page.get_by_role('button', name='Skjul', exact=True).wait_for()
            browser.close()
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
