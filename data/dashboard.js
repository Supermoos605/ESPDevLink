(() => {
  const ids = ['dashConnection','dashHost','dashGame','dashLatency','dashVideo','dashAudio','dashReconnects','dashError'];
  const el = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
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
    let connection = rawState;
    if (rawState === 'ERROR' && attempts > 0 && attempts < maxAttempts) connection = 'RECONNECTING';
    if (rawState === 'ERROR' && attempts >= maxAttempts) connection = 'OFFLINE';
    set('dashConnection', connection);
    set('dashHost', window.ESPLinkHostBase?.replace(/^https?:\/\//, '') || 'Not connected');
    set('dashGame', document.getElementById('gameName')?.textContent || selectedGame || 'Desktop');
    set('dashAudio', video?.muted ? 'Muted' : 'Enabled');
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