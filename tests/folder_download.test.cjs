const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');

for (const mobile of [false, true]) {
  for (const mode of ['original', 'converted']) {
    for (const dateMode of ['original', 'today']) {
      test(`folder ZIP: mobile=${mobile}, ${mode}, ${dateMode}`, async () => {
        const requests = [];
        const context = vm.createContext({
          state: { mapperSelectedPhotoIds: new Set([999]), mapperSelectedFolders: new Set(['Other']) },
          els: { mapperDownloadModal: { classList: { add() {}, remove() {} } } },
          AbortController, Set, console, clearTimeout,
          isMobileDownloadDevice: () => mobile,
          getMapperDownloadDateMode: () => dateMode,
          tr: key => key,
          _downloadStatusTimer: null, _downloadInProgress: false, _activeDownloadController: null,
          _fetchBlobWithProgress: async (url, init) => {
            requests.push({ url, body: JSON.parse(init.body) });
            return { ok: true, blob: {}, res: { headers: { get: () => '' } } };
          },
          _extractFilenameFromDisposition: () => 'folder.zip',
        });
        for (const name of ['_clearPreparedMobileDownloads', 'updateMapperDownloadHint',
          '_setMapperDownloadControlsBusy', 'showDownloadTopStatusMessage', 'setDownloadTopStatusIndeterminate',
          'setDownloadTopStatusCancelable', '_scheduleDownloadStatusHide', '_downloadFileFromBlob']) context[name] = () => {};
        context.showStatus = message => { throw new Error(message); };
        vm.runInContext(source.slice(source.indexOf('let _mapperDownloadFolders'), source.indexOf('let _downloadStatusTimer')), context);
        vm.runInContext(source.slice(source.indexOf('async function runMapperDownload'), source.indexOf('async function sharePreparedMobileDownloads')), context);
        vm.runInContext(source.slice(source.indexOf('function startMapperDownloadFromModal'), source.indexOf('function showDnsStatus')), context);
        context.openDownloadModal('Album/Family');
        context.startMapperDownloadFromModal(mode);
        await new Promise(resolve => setImmediate(resolve));
        assert.deepEqual(JSON.parse(JSON.stringify(requests)), [{ url: '/api/photos/download-zip', body: {
          photo_ids: [], folders: ['Album/Family'], mode, date_mode: dateMode,
        } }]);
        context.closeDownloadModal();
        context.openDownloadModal();
        assert.deepEqual(Array.from(vm.runInContext('_mapperDownloadFolders', context)), ['Other']);
        assert.deepEqual(Array.from(vm.runInContext('_mapperDownloadPhotoIds', context)), [999]);
      });
    }
  }
}
