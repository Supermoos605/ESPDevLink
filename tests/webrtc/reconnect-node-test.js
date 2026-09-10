const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('data/webrtc-reconnect.js', 'utf8');
const timers = new Set();
const fakeWindow = {};
const context = {
  window: fakeWindow,
  setTimeout(callback, delay) {
    const timer = setTimeout(() => { timers.delete(timer); callback(); }, delay);
    timers.add(timer);
    return timer;
  },
  clearTimeout(timer) { clearTimeout(timer); timers.delete(timer); },
};
vm.runInNewContext(source, context, { filename: 'data/webrtc-reconnect.js' });

const helper = fakeWindow.ESPLinkReconnect;
assert.ok(helper);
assert.equal(helper.attempts, 0);
assert.equal(helper.maxAttempts, 5);

let calls = 0;
helper.schedule(() => { calls += 1; });
assert.equal(helper.attempts, 1);

setTimeout(() => {
  assert.equal(calls, 1);
  helper.reset();
  assert.equal(helper.attempts, 0);
  helper.schedule(() => { calls += 1; });
  helper.cancel();
  setTimeout(() => {
    assert.equal(calls, 1);
    for (const timer of timers) clearTimeout(timer);
    console.log('Reconnect helper tests passed');
  }, 1200);
}, 1200);
