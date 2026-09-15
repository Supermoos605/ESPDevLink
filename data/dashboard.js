(() => {
  const ids = ['dashConnection','dashHost','dashGame','dashLatency','dashVideo','dashAudio','dashReconnects','dashError'];
  const el = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
  const dot = document.getElementById('stateDot');
  if (!el.dashConnection) return;
  let lastError = 'None';
  const set = (key, value) => { if (el[key]) el[key].textContent = value; };
  const update = async () => {
    const video = document.getElementById('stream');
    const state = document.getElementById('state');
    const selectedGame = localStorage.getItem('espLinkSelectedGame');
    const rawState = state?.textContent || 'READY';
    const attempts = typeof window.ESPLinkReconnect?.attempts === 'function' ? window.ESPLinkReconnect.attempts() : 0;
    const maxAttempts = Number(window.ESPLinkReconnect?.maxAttempts || 5);
    const route = window.ESPLinkConnectionMode;
    const requestedMode = window.ESPLinkRequestedConnectionMode || route;
    const transition = window.ESPLinkConnectionTransition;
    let connection = route && route !== 'DETECTING' ? route : rawState;
    if (transition === 'FALLBACK') connection = 'SWITCHING';
    else if (requestedMode === 'FORCE_REMOTE') connection = 'FORCED REMOTE';
    else if (route === 'REMOTE') connection = 'REMOTE';
    else if (route === 'LOCAL') connection = 'LOCAL';
    else if (route === 'AUTOMATIC') connection = 'AUTOMATIC';
    if (rawState === 'ERROR' && attempts > 0 && attempts < maxAttempts) connection = 'RECONNECTING';
    if (rawState === 'ERROR' && attempts >= maxAttempts) connection = 'OFFLINE';
    set('dashConnection', connection);
    if (dot) {
      dot.className = 'dot ' + connection.toLowerCase();
      dot.setAttribute('aria-label', `Connection ${connection.toLowerCase()}`);
    }
    // In remote mode ESPLinkHostBase is the tunnel URL, not the computer's
    // identity. Prefer the host name cached by the connection flow and only
    // fall back to the URL when no identity has been discovered yet.
    const savedHostName = localStorage.getItem('espLinkHostName') || localStorage.getItem('espLinkComputerName');
    const hostDisplay = savedHostName || window.ESPLinkHostName || window.ESPLinkHostBase?.replace(/^https?:\/\//, '') || 'Not connected';
    set('dashHost', hostDisplay);
    set('dashGame', document.getElementById('gameName')?.textContent || selectedGame || 'Desktop');
    const audio = document.querySelector('audio[data-esplink-audio]') || document.querySelector('audio');
    set('dashAudio', audio?.muted ? 'Muted' : 'Enabled');
    set('dashReconnects', attempts ? `${attempts}/${maxAttempts}` : '0');
    set('dashLatency', 'Unavailable');
    if (video?.videoWidth && video?.videoHeight) set('dashVideo', `${video.videoWidth}×${video.videoHeight}`);
    else set('dashVideo', 'Waiting');
    const peer = window.ESPLinkPeer;
    if (peer && typeof peer.getStats === 'function') {
      try {
        const stats = await peer.getStats();
        stats.forEach(report => {
          if (report.type === 'candidate-pair' && (report.state === 'succeeded' || report.nominated) && report.currentRoundTripTime != null) set('dashLatency', `${Math.round(report.currentRoundTripTime * 1000)} ms`);
          if (report.type === 'inbound-rtp' && (report.kind === 'video' || report.mediaType === 'video')) {
            const width = report.frameWidth || video?.videoWidth;
            const height = report.frameHeight || video?.videoHeight;
            const fps = report.framesPerSecond;
            if (width && height) set('dashVideo', `${width}×${height}${fps ? ` · ${Math.round(fps)} FPS` : ''}`);
          }
        });
      } catch (_) {}
    }
    set('dashError', lastError);
  };
  window.ESPLinkDashboard = {
    update,
    setError: message => { lastError = message || 'Unknown error'; update(); },
    clearError: () => { lastError = 'None'; update(); }
  };
  update();
  setInterval(update, 1000);
})();