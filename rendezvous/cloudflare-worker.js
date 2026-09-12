// ESPDevLink rendezvous service for Cloudflare Workers.
// Bind a KV namespace as R2? No: use the KV binding named ESPDEVLINK_KV.
// Set REGISTRATION_TOKEN as a Worker secret.
//
// Routes:
//   POST /api/register  (Bearer token required)
//   GET  /api/lookup/<device_id>
// Records are short-lived via expiration on each write.

const json = (status, body) => new Response(JSON.stringify(body), {
  status,
  headers: {
    "Content-Type": "application/json",
    "Cache-Control": "no-store",
  },
});

function authorized(request, env) {
  const value = request.headers.get("Authorization") || "";
  return value.startsWith("Bearer ") &&
    value.slice(7).trim() === env.REGISTRATION_TOKEN;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "POST" && url.pathname === "/api/register") {
      if (!authorized(request, env)) return json(401, { ok: false, error: "unauthorized" });

      let body;
      try {
        body = await request.json();
      } catch {
        return json(400, { ok: false, error: "invalid JSON" });
      }

      const deviceId = String(body.device_id || "").trim();
      const publicUrl = String(body.url || "").trim();

      if (!deviceId || deviceId.length > 64) {
        return json(400, { ok: false, error: "invalid device_id" });
      }
      if (!/^https:\/\/[^\s]+$/i.test(publicUrl) || publicUrl.length > 512) {
        return json(400, { ok: false, error: "url must be HTTPS" });
      }

      const ttl = Math.max(30, Number(env.RECORD_TTL || 120));
      const expiresAt = Math.floor(Date.now() / 1000) + ttl;

      await env.ESPDEVLINK_KV.put(
        deviceId,
        JSON.stringify({ url: publicUrl, expires_at: expiresAt }),
        { expirationTtl: ttl }
      );

      return json(200, { ok: true, device_id: deviceId, expires_at: expiresAt });
    }

    if (request.method === "GET" && url.pathname.startsWith("/api/lookup/")) {
      const deviceId = decodeURIComponent(url.pathname.slice("/api/lookup/").replace(/^\/+|\/+$/g, ""));
      if (!deviceId || deviceId.length > 64) {
        return json(400, { ok: false, error: "invalid device_id" });
      }

      const raw = await env.ESPDEVLINK_KV.get(deviceId);
      if (!raw) return json(200, { ok: true, online: false, url: null });

      let record;
      try {
        record = JSON.parse(raw);
      } catch {
        return json(200, { ok: true, online: false, url: null });
      }

      if (record.expires_at <= Math.floor(Date.now() / 1000)) {
        await env.ESPDEVLINK_KV.delete(deviceId);
        return json(200, { ok: true, online: false, url: null });
      }

      return json(200, {
        ok: true,
        online: true,
        url: record.url,
        expires_at: record.expires_at,
      });
    }

    return json(404, { ok: false, error: "not found" });
  },
};
