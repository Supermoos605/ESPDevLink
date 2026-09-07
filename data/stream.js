const video = document.getElementById('stream');
const placeholder = document.getElementById('placeholder');
const gameName = document.getElementById('gameName');
const hint = document.getElementById('gameHint');
const meta = document.getElementById('hostMeta');
const state = document.getElementById('state');

video.autoplay = true;
video.muted = true;
video.playsInline = true;

let hostBase = '';
let hostSession = '';
let peerId = null;
let peer = null;
let inputChannel = null;
let signalTimer = null;
let stopped = false;
let inputBound = false;

const pressedKeys = new Set();
const pressedButtons = new Set();

const labels = {
  ready: 'READY',
  connecting: 'CONNECTING',
  streaming: 'LIVE',
  error: 'ERROR',
  offline: 'OFFLINE',
};

function paint(s) {
  const label = labels[s.state] || 'READY';
  state.textContent = label;
  gameName.textContent = s.game || localStorage.getItem('espLinkSelectedGame') || 'Desktop';
  meta.textContent = `${s.game || 'Desktop'} · ${label}`;

  if (s.state === 'streaming' && video.srcObject) {
    placeholder.style.display = 'none';
  } else {
    placeholder.style.display = 'block';
    hint.textContent = s.state === 'connecting'
      ? 'Waiting for the host to start the stream.'
      : s.state === 'error'
        ? 'The streaming session reported an error.'
        : 'Connect to the host to begin.';
  }
}

async function request(base, path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (base === hostBase && hostSession) {
    headers['X-ESPLink-Host-Session'] = hostSession;
  }

  const response = await fetch(base + path, {
    cache: 'no-store',
    ...options,
    headers,
  });

  if (!response.ok) {
    throw new Error(
      (await response.json().catch(() => ({}))).error || `HTTP ${response.status}`,
    );
  }

  return response.json();
}

async function loginHost() {
  const code = window.prompt('Enter the Windows host authorization code:');
  if (!code) throw new Error('Host authorization code is required.');

  const login = await request(hostBase, '/api/auth', {
    method: 'POST',
    body: JSON.stringify({ code, client_id: `browser-${Date.now()}` }),
  });

  hostSession = login.session_id;
  if (!hostSession) throw new Error('The Windows host did not return a session.');
}

async function connectHost() {
  const pc = await request('', '/api/pc');
  if (!pc || !pc.ip) throw new Error('The ESP32 did not provide the host IP address.');

  hostBase = `http://${pc.ip}:8765`;
  hostSession = '';
  await loginHost();

  const selected = localStorage.getItem('espLinkSelectedGame') || 'Test Stream';
  try {
    return await request(hostBase, '/api/connect', {
      method: 'POST',
      body: JSON.stringify({ game: selected, session_id: hostSession }),
    });
  } catch (error) {
    if (error.message.toLowerCase().includes('session')) {
      hostSession = '';
      await loginHost();
      return request(hostBase, '/api/connect', {
        method: 'POST',
        body: JSON.stringify({ game: selected, session_id: hostSession }),
      });
    }
    throw error;
  }
}

function sendInput(type, action, data = {}) {
  if (inputChannel && inputChannel.readyState === 'open') {
    inputChannel.send(JSON.stringify({ type, action, data }));
  }
}

function pointerData(event) {
  const rect = video.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
    y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    button: event.button === 2 ? 'right' : event.button === 1 ? 'middle' : 'left',
    pointer_type: event.pointerType || 'mouse',
  };
}

function bindInput() {
  if (inputBound) return;
  inputBound = true;

  document.addEventListener('keydown', (event) => {
    if (stopped || ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;

    if (!pressedKeys.has(event.code)) {
      pressedKeys.add(event.code);
      sendInput('key', 'down', {
        code: event.code,
        key: event.key,
        repeat: event.repeat,
      });
    }
    event.preventDefault();
  });

  document.addEventListener('keyup', (event) => {
    if (stopped) return;
    pressedKeys.delete(event.code);
    sendInput('key', 'up', { code: event.code, key: event.key });
    event.preventDefault();
  });

  video.addEventListener('pointermove', (event) => {
    if (!stopped) sendInput('mouse', 'move', pointerData(event));
  });

  video.addEventListener('pointerdown', (event) => {
    if (stopped) return;
    video.setPointerCapture?.(event.pointerId);
    const data = pointerData(event);
    pressedButtons.add(data.button);
    sendInput('mouse', 'down', data);
    event.preventDefault();
  });

  video.addEventListener('pointerup', (event) => {
    if (stopped) return;
    const data = pointerData(event);
    pressedButtons.delete(data.button);
    sendInput('mouse', 'up', data);
    event.preventDefault();
  });

  video.addEventListener('pointercancel', (event) => {
    if (stopped) return;
    const data = pointerData(event);
    pressedButtons.delete(data.button);
    sendInput('mouse', 'up', data);
    event.preventDefault();
  });

  video.addEventListener('wheel', (event) => {
    if (!stopped) {
      sendInput('mouse', 'wheel', {
        deltaX: event.deltaX,
        deltaY: event.deltaY,
      });
      event.preventDefault();
    }
  }, { passive: false });

  window.addEventListener('blur', releaseInput);
}

function releaseInput() {
  for (const code of pressedKeys) sendInput('key', 'up', { code });
  for (const button of pressedButtons) sendInput('mouse', 'up', { button });
  pressedKeys.clear();
  pressedButtons.clear();
}

async function createPeer() {
  const selected = localStorage.getItem('espLinkSelectedGame') || 'Desktop';
  const mode = selected === 'Test Stream' ? 'test' : 'desktop';
  let session;

  try {
    session = await request(hostBase, '/api/webrtc/session', {
      method: 'POST',
      body: JSON.stringify({ video_mode: mode, session_id: hostSession }),
    });
  } catch (error) {
    if (error.message.toLowerCase().includes('session') || error.message.includes('401')) {
      hostSession = '';
      await loginHost();
      session = await request(hostBase, '/api/webrtc/session', {
        method: 'POST',
        body: JSON.stringify({ video_mode: mode, session_id: hostSession }),
      });
    } else {
      throw error;
    }
  }

  peerId = session.peer_id;
  peer = new RTCPeerConnection();
  inputChannel = peer.createDataChannel('input', {
    ordered: false,
    maxRetransmits: 0,
  });

  inputChannel.onopen = () => {
    hint.textContent = 'Keyboard, mouse, and touch input enabled.';
  };
  inputChannel.onclose = releaseInput;
  inputChannel.onerror = (event) => console.warn('Input channel error:', event);

  bindInput();
  stopped = false;

  peer.ontrack = async (event) => {
    if (!event.streams[0]) return;

    video.srcObject = event.streams[0];
    placeholder.style.display = 'none';

    try {
      await video.play();
      paint({ state: 'streaming', game: selected });
    } catch (error) {
      console.error('[ESPLink] Video playback failed:', error);
      hint.textContent = 'Click the video to start playback.';
    }
  };

  video.onclick = () => {
    video.play().catch((error) => console.error('[ESPLink] Video playback failed:', error));
  };

  peer.onconnectionstatechange = () => {
    if (peer.connectionState === 'connected') paint({ state: 'streaming', game: selected });
    if (['failed', 'closed'].includes(peer.connectionState) && !stopped) {
      fail('The WebRTC connection failed.');
    }
  };

  peer.onicecandidate = (event) => {
    if (event.candidate) sendSignal({ type: 'ice-candidate', candidate: event.candidate.toJSON() });
  };

  const offer = await peer.createOffer({ offerToReceiveAudio: true, offerToReceiveVideo: true });
  await peer.setLocalDescription(offer);
  await sendSignal({ type: 'offer', sdp: offer.sdp });
  signalTimer = setInterval(receiveSignals, 500);
}

async function sendSignal(message) {
  await request(hostBase, '/api/webrtc/message', {
    method: 'POST',
    headers: { 'X-ESPLink-Peer': peerId },
    body: JSON.stringify(message),
  });
}

function fail(message) {
  stopped = true;
  releaseInput();
  clearInterval(signalTimer);
  signalTimer = null;
  if (peer) peer.close();
  peer = null;
  inputChannel = null;
  paint({ state: 'error', game: localStorage.getItem('espLinkSelectedGame') || 'Desktop' });
  hint.textContent = message;
  console.error(message);
}

async function receiveSignals() {
  if (stopped) return;

  try {
    const result = await request(hostBase, '/api/webrtc/messages', {
      headers: { 'X-ESPLink-Peer': peerId },
    });

    for (const message of result.messages || []) {
      if (message.type === 'answer' && peer && peer.signalingState !== 'stable') {
        await peer.setRemoteDescription({ type: 'answer', sdp: message.sdp });
      } else if (message.type === 'ice-candidate' && message.candidate) {
        await peer.addIceCandidate(message.candidate);
      } else if (message.type === 'error') {
        fail(message.message || 'The host could not create the requested stream.');
        return;
      }
    }
  } catch (error) {
    if (!stopped) console.warn('Signaling:', error.message);
  }
}

async function start() {
  try {
    paint({ state: 'connecting', game: localStorage.getItem('espLinkSelectedGame') || 'Test Stream' });
    await connectHost();
    await createPeer();
  } catch (error) {
    fail(error.message);
  }
}

async function stop() {
  stopped = true;
  releaseInput();
  clearInterval(signalTimer);
  signalTimer = null;
  if (peer) peer.close();
  peer = null;
  inputChannel = null;
  peerId = null;

  if (video.srcObject) {
    video.srcObject.getTracks().forEach((track) => track.stop());
    video.srcObject = null;
  }

  paint({ state: 'ready', game: '' });
}

document.getElementById('settings').onclick = () => { location.href = '/settings.html'; };
document.getElementById('disconnect').onclick = stop;
start();
