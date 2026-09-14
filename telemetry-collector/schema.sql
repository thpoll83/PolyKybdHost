-- PolyHost telemetry collector — D1 (SQLite) schema.
--
-- One row per install per UTC day. Raw rows are kept indefinitely: at a few
-- pings a day this is kilobytes a year, and a rollup you add later can always
-- be recomputed from raw rows, while detail you discarded is gone for good.
-- Add the daily-aggregate table when raw actually gets expensive.

CREATE TABLE IF NOT EXISTS ping (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  -- Server-assigned. The client deliberately sends no timestamp: one less
  -- field to trust, and a skewed client clock cannot land in the wrong day.
  received_at      TEXT    NOT NULL,
  day              TEXT    NOT NULL,          -- YYYY-MM-DD (UTC)

  install_id       TEXT    NOT NULL,
  schema_version   INTEGER NOT NULL,
  -- Derived from the connection at the edge and then discarded; the IP itself
  -- is never stored. Coarse enough to be non-identifying, useful for knowing
  -- which locales to care about.
  country          TEXT,

  host_version     TEXT,
  host_protocol    INTEGER,
  os               TEXT,
  os_release       TEXT,
  -- Linux window-stack census (schema 2+). '' on Windows/macOS, and '' for
  -- every row a schema-1 host wrote, which is why the migration below adds
  -- them with DEFAULT '' rather than leaving NULL: "never told us" and "told
  -- us nothing" are the same answer here, and one of them breaks GROUP BY.
  session          TEXT,                      -- x11 | wayland | other
  desktop          TEXT,                      -- gnome | kde | xfce | ... | other
  window_backend   TEXT,                      -- pywinctl | kde_win_reporter
                                              -- | gnome_wayland_reporter
  arch             TEXT,
  python           TEXT,
  mode             TEXT,                      -- daemon | in-process | headless

  device_present   INTEGER,
  device_connected INTEGER,
  device_name      TEXT,
  fw_version       TEXT,
  device_protocol  INTEGER,
  hw_version       TEXT,
  fontpack         TEXT,                      -- JSON {bundle: content_version}

  counters         TEXT,                      -- JSON {name: count}
  -- The CANONICAL row as JSON — i.e. exactly the allow-listed columns above,
  -- never the request body. ⚠️ It used to hold the body as received, which
  -- quietly defeated the whole allow-list: `validate()` only checks `schema`
  -- and `install_id`, so any extra field a caller invented would have been
  -- persisted here forever. Storing the rebuilt row keeps this queryable as one
  -- blob while making it impossible to retain a field we did not ask for. The
  -- cost is that an unknown field from a FUTURE schema is dropped rather than
  -- captured for later — which is the correct trade for a privacy feature: add
  -- the column when you add the field.
  raw              TEXT    NOT NULL
);

-- Dedupe AND rate limit in one: a second ping from the same install on the same
-- day is an INSERT OR IGNORE no-op, so a client bug (or someone replaying a
-- payload) cannot inflate the numbers or grow the table.
CREATE UNIQUE INDEX IF NOT EXISTS ping_install_day ON ping (install_id, day);

CREATE INDEX IF NOT EXISTS ping_day ON ping (day);
CREATE INDEX IF NOT EXISTS ping_host_version ON ping (host_version);

-- Daily actives split by host version — the question this whole thing exists
-- to answer.
CREATE VIEW IF NOT EXISTS daily_by_host_version AS
SELECT day, host_version, COUNT(*) AS installs
FROM ping GROUP BY day, host_version ORDER BY day DESC, installs DESC;

-- Which firmware is actually in the field, among installs that had a keyboard
-- attached that day.
CREATE VIEW IF NOT EXISTS daily_by_fw_version AS
SELECT day, fw_version, COUNT(*) AS installs
FROM ping WHERE device_present = 1 AND fw_version <> ''
GROUP BY day, fw_version ORDER BY day DESC, installs DESC;


-- ---------------------------------------------------------------------------
-- Migrations
-- ---------------------------------------------------------------------------
-- The CREATE TABLE above is IF NOT EXISTS, so it does nothing to a live table
-- that predates a column. Apply these by hand, once, against the deployed D1:
--
--   wrangler d1 execute polyhost-telemetry --remote \
--     --command "ALTER TABLE ping ADD COLUMN session TEXT NOT NULL DEFAULT ''"
--
-- D1 takes one ALTER per statement, so run the three separately. Each is a
-- no-op error ("duplicate column name") if already applied — safe to re-run.
--
-- schema 2 (payload session/desktop/window_backend):
--   ALTER TABLE ping ADD COLUMN session        TEXT NOT NULL DEFAULT '';
--   ALTER TABLE ping ADD COLUMN desktop        TEXT NOT NULL DEFAULT '';
--   ALTER TABLE ping ADD COLUMN window_backend TEXT NOT NULL DEFAULT '';
--
-- ⚠️ Apply the migration BEFORE deploying the worker. The worker's INSERT
-- names all three columns, so between a new worker and an un-migrated table
-- every ping fails with a 503 and the day's data is simply lost — pings are
-- daily and never retried, so it cannot be backfilled.
