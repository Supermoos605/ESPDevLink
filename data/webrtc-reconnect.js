/*
 * ESPLink WebRTC reconnect helper.
 *
 * This helper is intentionally isolated so it can be loaded by stream.html
 * without replacing the existing streaming implementation.
 */
(function () {
  'use strict';

  const MAX_ATTEMPTS = 5;
  const BASE_DELAY_MS = 1000;
  const MAX_DELAY_MS = 30000;

  let attempts = 0;
  let timer = null;

  function delayForAttempt(attempt) {
    return Math.min(MAX_DELAY_MS, BASE_DELAY_MS * (2 ** Math.max(0, attempt - 1)));
  }

  function clearReconnectTimer() {
    if (timer !== null) {
      window.clearTimeout(timer);
      timer = null;
    }
  }

  function resetReconnectAttempts() {
    attempts = 0;
    clearReconnectTimer();
  }

  function scheduleReconnect(callback, statusCallback) {
    if (typeof callback !== 'function' || timer !== null) return false;
    if (attempts >= MAX_ATTEMPTS) return false;

    attempts += 1;
    const delay = delayForAttempt(attempts);

    if (typeof statusCallback === 'function') {
      statusCallback({
        attempt: attempts,
        maxAttempts: MAX_ATTEMPTS,
        delay,
        message: `Connection lost. Retrying in ${Math.ceil(delay / 1000)} second${delay === 1000 ? '' : 's'}...`
      });
    }

    timer = window.setTimeout(() => {
      timer = null;
      callback();
    }, delay);

    return true;
  }

  window.ESPLinkReconnect = {
    schedule: scheduleReconnect,
    reset: resetReconnectAttempts,
    cancel: clearReconnectTimer,
    get attempts() {
      return attempts;
    },
    get maxAttempts() {
      return MAX_ATTEMPTS;
    }
  };
})();
