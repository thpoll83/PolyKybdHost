// The JupyterLab-free half (src/context.ts), compiled to build-test/ by `npm test`.
const test = require('node:test');
const assert = require('node:assert');
const { contextUrl, SendPolicy, reportBody, KEEPALIVE_MS } = require('../build-test/context.js');

test('notebook URL names the mode', () => {
  assert.strictEqual(contextUrl('notebook', 'command'), 'jupyter://notebook/command');
  assert.strictEqual(contextUrl('notebook', 'edit'), 'jupyter://notebook/edit');
  // An unknown mode reads as command mode, the notebook's default.
  assert.strictEqual(contextUrl('notebook', undefined), 'jupyter://notebook/command');
});

test('other activities', () => {
  assert.strictEqual(contextUrl('editor'), 'jupyter://editor');
  assert.strictEqual(contextUrl('console'), 'jupyter://console');
  assert.strictEqual(contextUrl('terminal'), 'jupyter://terminal');
  assert.strictEqual(contextUrl('other'), 'jupyter://other');
  assert.strictEqual(contextUrl('bogus'), 'jupyter://other');
});

test('send on change and keep alive only while focused', () => {
  const p = new SendPolicy(3000);
  assert.strictEqual(p.due('a', false, 0), false);   // unfocused page: nothing yet
  assert.strictEqual(p.due('a', true, 0), true);
  p.sent('a', true, 0);
  assert.strictEqual(p.due('a', true, 2999), false);
  assert.strictEqual(p.due('a', true, 3000), true);
  assert.strictEqual(p.due('b', true, 100), true);   // mode change
  assert.strictEqual(p.due('a', false, 100), true);  // focus lost: one report
  p.sent('a', false, 100);
  assert.strictEqual(p.due('a', false, 99999), false); // then silence
  assert.strictEqual(p.due('a', true, 99999), true);
});

test('report body sends no URL when unfocused', () => {
  assert.deepStrictEqual(JSON.parse(reportBody('jupyter://editor', true, 1.234)),
    { url: 'jupyter://editor', focused: true, input_age: 1.2 });
  assert.deepStrictEqual(JSON.parse(reportBody('jupyter://editor', false, -5)),
    { url: null, focused: false, input_age: 0 });
  assert.strictEqual(KEEPALIVE_MS, 3000);
});
