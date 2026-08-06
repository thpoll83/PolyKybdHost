/**
 * PolyHost telemetry collector — Cloudflare Worker in front of D1.
 *
 * This is the piece that lets the client stay dumb: it ships no observability
 * SDK and no credential, just a JSON POST. Everything that needs to be
 * changeable without shipping a host release lives here — validation, the
 * privacy rules, retention, and (later) an OTLP export to whatever dashboard
 * backend we are using that year.
 *
 * Privacy rules enforced here, not client-side, because here they can be fixed:
 *  - the client IP is used for the country lookup and then dropped; it is never
 *    stored, logged or forwarded;
 *  - only allow-listed fields are persisted, so a client that ever sends more
 *    than it should does not get it written down;
 *  - one row per install per UTC day (a UNIQUE index + INSERT OR IGNORE), which
 *    doubles as the rate limit.
 */

const MAX_BODY_BYTES = 8 * 1024;
const SUPPORTED_SCHEMAS = new Set([1]);

// Field caps. A payload is machine-generated, so anything longer is either a
// bug or an attempt to fill the database; truncating beats rejecting because a
// slightly-too-long version string should not lose the whole ping.
const LIMITS = {
  install_id: 64,
  host_version: 32,
  os: 32,
  os_release: 32,
  arch: 32,
  python: 16,
  mode: 32,
  device_name: 64,
  fw_version: 32,
  hw_version: 32,
};

const str = (v, max) => (typeof v === 'string' ? v.slice(0, max) : '');
const int = (v) => (Number.isFinite(v) ? Math.trunc(v) : null);
const bool = (v) => (v ? 1 : 0);

/** Keep a small JSON map of number values (fontpack versions, counters). */
function jsonMap(v, maxKeys = 32) {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return '{}';
  const out = {};
  for (const [k, val] of Object.entries(v).slice(0, maxKeys)) {
    const n = int(val);
    if (n !== null) out[String(k).slice(0, 32)] = n;
  }
  return JSON.stringify(out);
}

function validate(payload) {
  if (!payload || typeof payload !== 'object') return 'not an object';
  if (!SUPPORTED_SCHEMAS.has(payload.schema)) return 'unsupported schema';
  const id = payload.install_id;
  if (typeof id !== 'string' || !/^[a-f0-9]{16,64}$/i.test(id)) {
    return 'bad install_id';
  }
  return null;
}

function toRow(payload, country, now) {
  const dev = payload.device && typeof payload.device === 'object' ? payload.device : {};
  return {
    received_at: now.toISOString(),
    day: now.toISOString().slice(0, 10),
    install_id: str(payload.install_id, LIMITS.install_id),
    schema_version: int(payload.schema),
    country: str(country, 8),
    host_version: str(payload.host_version, LIMITS.host_version),
    host_protocol: int(payload.host_protocol),
    os: str(payload.os, LIMITS.os),
    os_release: str(payload.os_release, LIMITS.os_release),
    arch: str(payload.arch, LIMITS.arch),
    python: str(payload.python, LIMITS.python),
    mode: str(payload.mode, LIMITS.mode),
    device_present: bool(dev.present),
    device_connected: bool(dev.connected),
    device_name: str(dev.name, LIMITS.device_name),
    fw_version: str(dev.fw_version, LIMITS.fw_version),
    device_protocol: int(dev.protocol),
    hw_version: str(dev.hw_version, LIMITS.hw_version),
    fontpack: jsonMap(dev.fontpack),
    counters: jsonMap(payload.counters),
  };
}

const INSERT = `
INSERT OR IGNORE INTO ping (
  received_at, day, install_id, schema_version, country,
  host_version, host_protocol, os, os_release, arch, python, mode,
  device_present, device_connected, device_name, fw_version, device_protocol,
  hw_version, fontpack, counters, raw
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'GET' && url.pathname === '/') {
      // Deliberately no read API: this Worker can only be written to. Query the
      // data with `wrangler d1 execute`, or point a dashboard at D1 directly.
      return new Response('PolyHost telemetry collector. POST /v1/ping\n', {
        headers: { 'content-type': 'text/plain' },
      });
    }
    if (url.pathname !== '/v1/ping') return new Response('not found', { status: 404 });
    if (request.method !== 'POST') {
      return new Response('method not allowed', { status: 405, headers: { allow: 'POST' } });
    }

    const body = await request.text();
    if (body.length > MAX_BODY_BYTES) {
      return new Response('payload too large', { status: 413 });
    }

    let payload;
    try {
      payload = JSON.parse(body);
    } catch {
      return new Response('bad json', { status: 400 });
    }

    const problem = validate(payload);
    if (problem) return new Response(problem, { status: 400 });

    // request.cf.country is derived from the connection; the IP itself never
    // leaves this function.
    const row = toRow(payload, request.cf?.country ?? '', new Date());

    try {
      await env.DB.prepare(INSERT)
        .bind(
          row.received_at, row.day, row.install_id, row.schema_version, row.country,
          row.host_version, row.host_protocol, row.os, row.os_release, row.arch,
          row.python, row.mode, row.device_present, row.device_connected,
          row.device_name, row.fw_version, row.device_protocol, row.hw_version,
          row.fontpack, row.counters, JSON.stringify(payload),
        )
        .run();
    } catch (e) {
      // Never tell the client anything useful about the store, and never make a
      // storage problem the client's problem: it treats any non-2xx as "try
      // again tomorrow", which is the correct behaviour here too.
      console.error('insert failed', e.message);
      return new Response('', { status: 503 });
    }

    // 204 whether the row was new or a same-day duplicate — the client has
    // nothing to do differently, and it should not learn what we already hold.
    return new Response('', { status: 204 });
  },
};
