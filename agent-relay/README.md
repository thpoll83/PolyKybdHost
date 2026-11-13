# PolyHost agent relay

A Cloudflare Worker that carries the state of Claude Code **cloud sessions**
(claude.ai/code, also when opened in the desktop app) to the agent keys on the
keyboard. A cloud session runs in a VM that cannot reach the keyboard computer,
and the keyboard computer cannot be reached from outside. Both connect out to this
relay: the session's hooks post to it, and the host keeps a WebSocket to it.

The relay sees channel IDs, opaque session keys and ciphertext only. The session's
state, title, URL and ID are encrypted end to end by
[`polyhost/services/agents/cloud_hook.py`](../polyhost/services/agents/cloud_hook.py)
with a key that only the host and the user's cloud environment have.

## How a user sets it up

The host part ("AI Agents → Connect Cloud Sessions…") creates a channel and shows a
configuration string. In the claude.ai cloud environment's settings:

1. **Environment variable:** `POLYKYBD_CLOUD_RELAY` = the string the host shows.
   Use a personal environment: its variables are visible to everyone who uses it.
2. **Allowed hosts** (when the network access is Limited):
   `polyhost-agent-relay.polykybd.workers.dev`
3. **Setup script:**

   ```bash
   curl -fsSL https://polyhost-agent-relay.polykybd.workers.dev/v1/hook.py \
       -o /usr/local/bin/polykybd-cloud-hook \
     && python3 /usr/local/bin/polykybd-cloud-hook --install || true
   ```

   `--install` adds the hooks to the VM's `~/.claude/settings.json` and keeps what
   is there. The `|| true` matters: a failing setup script stops the session from
   starting, and the agent keys are not worth that.

Each new cloud session of that environment then shows on a number key. The hook
sends a report only when the session's state changes.

## Endpoints

| | | |
|---|---|---|
| `GET /` | | banner (deploy smoke test) |
| `GET /v1/hook.py` | | the hook script |
| `POST /v1/channels` | | `{channel, read_hash, write_hash}`: create a channel |
| `POST /v1/c/<channel>/event` | write token | `{k, blob, ended}`: one report |
| `GET /v1/c/<channel>/state` | read token | the current reports |
| `GET /v1/c/<channel>/ws` | read token | WebSocket: a snapshot, then each report |
| `DELETE /v1/c/<channel>` | read token | delete the channel |

Tokens go as `Authorization: Bearer <64 hex>`. The relay stores only their
SHA-256 hashes.

## Limits

The Workers Free plan allows 100,000 Worker requests and 100,000 Durable Object
requests a day, for the whole account (the telemetry Worker included). One report
costs one of each. Per channel:

| limit | value |
|---|---|
| reports per day | 2,000 |
| reports per minute | 30 |
| sessions kept | 64, each for 24 h after its last report |
| host connections | 4 |
| one report | 4,096 characters |
| channels created per client IP | 5 a minute |

`polykybd-telemetry-data`'s usage check reads the account's counts every 3 hours
and fails its run at 80 % of either daily limit, which is the alert.

## Deploy and test

`.github/workflows/deploy-agent-relay.yml` deploys on a push to `main` that
touches this folder or `cloud_hook.py`, with the same secrets as the telemetry
Worker. On a pull request it builds without credentials and runs
`test/e2e_test.py` against `wrangler dev`. Locally:

```bash
cd agent-relay
npx --yes wrangler@4.119.0 dev --port 8799 --ip 127.0.0.1 &
python3 test/e2e_test.py -v
```
