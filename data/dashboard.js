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
    set('dashConnection', state?.textContent || 'READY');
    set('dashHost', window.ESPLinkHostBase?.replace(/^https?:\/\//, '') || 'Not connected');
    set('dashGame', document.getElementById('gameName')?.textContent || selectedGame || 'Desktop');
    set('dashAudio', video?.muted ? 'Muted' : 'Enabled');
    set('dashReconnects', String(typeof window.ESPLinkReconnect?.attempts === 'function' ? window.ESPLinkReconnect.attempts() : 0));
    set('dashLatency', 'Unavailable');
    if (video?.videoWidth && video?.videoHeight) set('dashVideo', `${video.videoWidth}×${video.videoHeight}`);
    else set('dashVideo', 'Waiting');
    const peer = window.ESPLinkPeer;
    if (peer && typeof peer.getStats === 'function') {
      try {
        const stats = await peer.getStats();
        stats.forEach(report => {
          if (report.type === 'candidate-pair' && report.state === 'succeeded' && report.currentRoundTripTime != null) set('dashLatency', `${Math.round(report.currentRoundTripTime * 1000)} ms`);
          if (report.type === 'inbound-rtp' && (report.kind === 'video' || report.mediaType === 'video') && report.framesPerSecond) set('dashVideo', `${report.frameWidth || video.videoWidth}×${report.frameHeight || video.videoHeight} · ${Math.round(report.framesPerSecond)} FPS`);
        });
      } catch (_) {}
    }
    set('dashError', lastError);
  };
  window.ESPLinkDashboard = { update, setError: message => { lastError = message || 'Unknown error'; update(); } };
  update();
  setInterval(update, 1000);
})();