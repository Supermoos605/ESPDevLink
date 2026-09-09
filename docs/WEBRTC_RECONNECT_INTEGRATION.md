# WebRTC reconnect integration

The reconnect helper is stored in `data/webrtc-reconnect.js`.

## Add it to `data/stream.html`

Place this script tag immediately before the existing `stream.js` script tag:

```html
<script src="/webrtc-reconnect.js"></script>
<script src="/stream.js"></script>
```

## Connect it in `data/stream.js`

Add these variables near the other connection state variables:

```js
let reconnectTimer = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;
```

Add this function:

```js
function scheduleReconnect(reason) {
  if (stopped || reconnectTimer || reconnectAttempts >= maxReconnectAttempts) {
    if (reconnectAttempts >= maxReconnectAttempts) {
      fail(reason || 'The stream could not reconnect.');
    }
    return;
  }

  reconnectAttempts += 1;
  const delay = Math.min(1000 * (2 ** (reconnectAttempts - 1)), 30000);
  diag('reconnect scheduled', `${reconnectAttempts}/${maxReconnectAttempts} in ${delay}ms`);
  paint({ state: 'connecting', game: localStorage.getItem('espLinkSelectedGame') || 'Desktop' });

  reconnectTimer = setTimeout(async () => {
    reconnectTimer = null;
    try {
      await start();
    } catch (error) {
      scheduleReconnect(error.message);
    }
  }, delay);
}
```

When the peer reaches `connected`, reset the counter:

```js
reconnectAttempts = 0;
```

When the peer enters `failed` or `closed`, call:

```js
scheduleReconnect('The WebRTC connection failed.');
```

Finally, clear the timer inside both `stop()` and `fail()`:

```js
clearTimeout(reconnectTimer);
reconnectTimer = null;
```

This document is intentionally separate from the live script so the existing streaming code is not overwritten until the complete file can be safely updated.
