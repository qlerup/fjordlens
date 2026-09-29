const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

test('cancel clears folder badges and highlights while normal refreshes reuse cards', async () => {
  const source = fs.readFileSync(path.join(__dirname, '../static/app.js'), 'utf8');
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    const result = await page.evaluate(({ render, cancel }) => {
      document.body.innerHTML = '<div id="grid" data-mapper-path="A"></div>';
      const grid = document.getElementById('grid');
      window.state = {
        view: 'mapper', mapperPath: 'A', mapperEditMode: true, items: [],
        mapperFolders: ['A/One', 'A/Two', 'A/Three', 'A/Four'],
        mapperSelectedFolders: new Set(['A/One', 'A/Two', 'A/Three']),
        mapperSelectedPhotoIds: new Set([42]),
      };
      window.els = { grid };
      window.mapperCardItemJson = new WeakMap();
      window.pendingMapperView = null;
      window.FjordLensFolderPreviews = { reset() {}, resume() {} };
      for (const name of ['renderMapperContext', '_stopMapperDragSelectSession', 'hideEmpty',
        'setDetail', 'renderStats', 'appendMapperGhostSlots', 'appendPhotoLoadMoreButton']) {
        window[name] = () => {};
      }
      window.isPagedGalleryView = () => true;
      window.mapperImmediateChildFolder = folder => folder;
      window.estimateMapperGridMetrics = () => ({ cols: 4 });
      window.mapperDisplayCapacity = () => 0;
      window.appendFolderCard = folder => {
        const card = document.createElement('article');
        card.className = 'photo-card folder-card';
        card.dataset.folder = folder;
        card.dataset.previewKey = 'null';
        if (state.mapperEditMode) {
          card.innerHTML = '<span class="folder-select-badge"></span>';
          if (state.mapperSelectedFolders.has(folder)) {
            card.classList.add('selected');
            card.firstChild.textContent = '\u2713';
          }
        }
        grid.append(card);
      };
      window.eval(render);
      window.eval(cancel);
      renderGrid();
      const selectedBefore = grid.querySelectorAll('.selected').length;
      setMapperEditMode(false);
      const clean = grid.querySelectorAll('.selected, .folder-select-badge').length === 0;
      const cards = [...grid.children];
      renderGrid();
      const reused = cards.every((card, i) => card === grid.children[i]);
      setMapperEditMode(true);
      const badgesOnReentry = grid.querySelectorAll('.folder-select-badge').length;
      const selectedOnReentry = grid.querySelectorAll('.selected').length;
      return { selectedBefore, clean, reused, badgesOnReentry, selectedOnReentry,
        foldersSelected: state.mapperSelectedFolders.size, photosSelected: state.mapperSelectedPhotoIds.size };
    }, {
      render: source.slice(source.indexOf('function renderGrid()'), source.indexOf('function appendCardTo(')),
      cancel: source.slice(source.indexOf('function setMapperEditMode('), source.indexOf('const MAPPER_DRAG_SELECT_MIN_DISTANCE_PX')),
    });
    assert.deepEqual(result, { selectedBefore: 3, clean: true, reused: true,
      badgesOnReentry: 4, selectedOnReentry: 0, foldersSelected: 0, photosSelected: 0 });
  } finally {
    await browser.close();
  }
});
