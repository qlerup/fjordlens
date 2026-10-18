const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

test('nearest explicit folder grant overrides inherited permissions for every storage variant', () => {
  const source = readFileSync(require('node:path').join(__dirname, '../static/app.js'), 'utf8');
  const context = vm.createContext({state: {currentUser: {role: 'user',
    owned_folders: ['uploads/Family/ReadOnly'],
    allowed_folders: [
      {folder_path: 'Family', permission: 'edit'},
      {folder_path: 'uploads/Family/ReadOnly', permission: 'view'},
      {folder_path: 'uploads/Family/ReadOnly/Inbox', permission: 'upload'},
      {folder_path: 'uploads', permission: 'edit'},
    ]}}});
  vm.runInContext(source.slice(source.indexOf('function mediaPathPermission('), source.indexOf('function mapperFolderCanDelete(')), context);
  for (const prefix of ['uploads/', 'uploads/originals/', 'uploads/converted/']) {
    for (const [suffix, expected] of [['Other/Deep/a.jpg', 'edit'], ['ReadOnly/Deep/a.jpg', 'view'], ['ReadOnly/Inbox/Deep/a.jpg', 'upload']]) {
      assert.equal(context.mediaPathPermission(prefix + 'Family/' + suffix), expected);
    }
  }
  assert.equal(context.mediaPathPermission('uploads/FamilySibling/a.jpg'), null);
  assert.equal(context.mapperFolderAllows('Family/ReadOnly/Deep', 'upload'), false);
  assert.equal(context.mapperFolderAllows('Family/ReadOnly/Inbox/Deep', 'upload'), true);
});
