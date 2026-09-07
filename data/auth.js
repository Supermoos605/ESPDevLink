(() => {
  const session = () => localStorage.getItem('espLinkSession') || '';
  const originalFetch = window.fetch.bind(window);
  const espOrigin = window.location.origin;
  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input.url;
    const requestUrl = new URL(url, window.location.href);
    const isSameOrigin = requestUrl.origin === espOrigin;
    const isAuthRequest = requestUrl.pathname.includes('/api/auth');
    const headers = new Headers(init.headers || (typeof input !== 'string' ? input.headers : undefined));
    const sid = session();
    if (sid && isSameOrigin && !isAuthRequest) headers.set('X-ESPLink-Session', sid);
    const response = await originalFetch(input, {...init, headers});
    if (response.status === 401 && isSameOrigin && !isAuthRequest && !location.pathname.endsWith('/auth.html')) {
      localStorage.removeItem('espLinkSession');
      location.replace('/auth.html');
    }
    return response;
  };
  if (!location.pathname.endsWith('/auth.html')) {
    const sid = session();
    if (!sid) location.replace('/auth.html');
  }
})();
