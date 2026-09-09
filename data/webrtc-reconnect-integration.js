// ESPDevLink WebRTC reconnect integration
// Paste these additions into data/stream.js.

let reconnectTimer = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

function clearReconnectTimer() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function scheduleReconnect(reason) {
  if (stopped || reconnectTimer || reconnectAttempts >= maxReconnectAttempts) {
    if (reconnectAttempts >= maxReconnectAttempts) {
      fail(reason || 'The WebRTC connection could not be restored.');
    }
    return;
  }

  reconnectAttempts += 1;
  const delay = Math.min(30000, 1000 * (2 ** (reconnectAttempts - 1)));
  diag('reconnect scheduled', `${reconnectAttempts}/${maxReconnectAttempts} in ${delay} ms`);
  hint.textContent = `Connection lost. Retrying in ${Math.ceil(delay / 1000)} seconds...`;

  clearInterval(signalTimer);
  signalTimer = null;
  releaseInput();
  if (peer) peer.close();
  peer = null;
  inputChannel = null;
  peerId = null;

  reconnectTimer = setTimeout(async () => {
    reconnectTimer = null;
    if (stopped) return;
    try {
      connecting = false;
      await start();
    } catch (error) {
      scheduleReconnect(error.message);
    }
  }, delay);
}

// In the RTCPeerConnection connection-state handler, replace the failure branch with:
// if (['failed', 'disconnected', 'closed'].includes(peer.connectionState) && !stopped) {
//   scheduleReconnect('The WebRTC connection failed.');
// }

// When the connection becomes connected, add:
// reconnectAttempts = 0;
// clearReconnectTimer();

// In stop() and fail(), add:
// clearReconnectTimer();
// reconnectAttempts = 0;
