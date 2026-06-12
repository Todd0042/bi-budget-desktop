"""bi-budget sync client — shared by the desktop and Android apps.

Pure stdlib (urllib/json/hashlib) so it adds nothing to the Flet Android bundle.
Whole-file, last-write-wins sync against the bi-budget-sync server.

This file is the SOURCE OF TRUTH. It is copied verbatim to:
  - bi-budget/src/core/sync.py            (Android, reused via core)
  - bi-budget-desktop/bi_budget_desktop/sync.py
Keep all three identical.

State files (next to the DB, never sent to the server):
  <db>.syncmeta   {synced_version, local_clean_sha}  — what server version we match,
                  and the local file's hash when last in sync (after any init_db write).
  sync_config.json (path passed in) {url, token, auto}

Change detection:
  remote_changed = server version != synced_version            (monotonic, reliable)
  local_changed  = sha256(local db) != local_clean_sha         (user edited since sync)
Onboarding: a never-synced device with a populated server PULLS (adopts it), backing up
any local db first — so a fresh install can't clobber the server with its empty default.
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_TIMEOUT = 12


class SyncError(Exception):
    pass


# --- config -----------------------------------------------------------------
def load_config(config_path):
    try:
        with open(config_path) as f:
            c = json.load(f)
    except (OSError, ValueError):
        c = {}
    return {
        "url": (c.get("url") or "").rstrip("/"),
        "token": c.get("token") or "",
        "auto": bool(c.get("auto", True)),
    }


def save_config(config_path, url, token, auto=True):
    tmp = config_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"url": (url or "").rstrip("/"), "token": token or "", "auto": bool(auto)}, f)
    os.replace(tmp, config_path)


def configured(config_path):
    return bool(load_config(config_path)["url"])


# --- sidecar ----------------------------------------------------------------
def _sidecar_path(db_path):
    return db_path + ".syncmeta"


def _load_sidecar(db_path):
    try:
        with open(_sidecar_path(db_path)) as f:
            c = json.load(f)
            return {"synced_version": int(c.get("synced_version", 0)),
                    "local_clean_sha": c.get("local_clean_sha", "")}
    except (OSError, ValueError):
        return {"synced_version": 0, "local_clean_sha": ""}


def _save_sidecar(db_path, synced_version, local_clean_sha):
    tmp = _sidecar_path(db_path) + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"synced_version": int(synced_version), "local_clean_sha": local_clean_sha}, f)
    os.replace(tmp, _sidecar_path(db_path))


# --- helpers ----------------------------------------------------------------
def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _request(method, url, token, data=None, extra_headers=None, timeout=DEFAULT_TIMEOUT):
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    if data is not None:
        req.add_header("Content-Type", "application/octet-stream")
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), {k: v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, e.read(), {k: v for k, v in e.headers.items()}
    except (urllib.error.URLError, OSError) as e:
        raise SyncError("network unreachable: %s" % e)


def _get_meta(cfg, timeout=DEFAULT_TIMEOUT):
    status, body, _ = _request("GET", cfg["url"] + "/meta", cfg["token"], timeout=timeout)
    if status == 401:
        raise SyncError("unauthorized — check the sync token")
    if status != 200:
        raise SyncError("meta returned HTTP %s" % status)
    try:
        return json.loads(body.decode() or "{}")
    except ValueError:
        raise SyncError("bad meta response")


def _backup(db_path):
    if os.path.exists(db_path):
        bak = "%s.conflict-%d" % (db_path, int(time.time()))
        try:
            with open(db_path, "rb") as s, open(bak, "wb") as d:
                d.write(s.read())
            return bak
        except OSError:
            pass
    return None


def _push(cfg, db_path, local_mtime, conflict=False, timeout=DEFAULT_TIMEOUT):
    with open(db_path, "rb") as f:
        data = f.read()
    status, body, _ = _request("PUT", cfg["url"] + "/db", cfg["token"], data=data,
                               extra_headers={"X-Client-Mtime": repr(local_mtime)}, timeout=timeout)
    if status != 200:
        raise SyncError("push returned HTTP %s: %s" % (status, body[:120]))
    try:
        meta = json.loads(body.decode())
    except ValueError:
        raise SyncError("bad push response")
    _save_sidecar(db_path, meta["version"], _sha256_file(db_path))
    return {"status": "pushed-conflict" if conflict else "pushed", "detail": "v%s" % meta["version"]}


def _pull(cfg, db_path, on_pulled, timeout=DEFAULT_TIMEOUT):
    status, body, headers = _request("GET", cfg["url"] + "/db", cfg["token"], timeout=timeout)
    if status != 200:
        raise SyncError("pull returned HTTP %s" % status)
    if body[:16] != b"SQLite format 3\x00":
        raise SyncError("pulled data is not a SQLite database")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    tmp = db_path + ".pull.tmp"
    with open(tmp, "wb") as f:
        f.write(body)
    os.replace(tmp, db_path)
    version = int(headers.get("X-Version", "0") or 0)
    # on_pulled (e.g. init_db migrations) may write to the file → fold that into the
    # clean hash so it isn't mistaken for a local edit on the next sync.
    if on_pulled:
        try:
            on_pulled()
        except Exception:
            pass
    _save_sidecar(db_path, version, _sha256_file(db_path))
    return {"status": "pulled", "detail": "v%s" % version}


# --- the one entry point ----------------------------------------------------
def sync(db_path, config_path, on_pulled=None, timeout=DEFAULT_TIMEOUT):
    """Reconcile the local DB with the server. Returns {status, detail}.
    status ∈ {disabled, in-sync, pushed, pulled, pushed-conflict, pulled-conflict, error}.
    Never raises — network/server problems come back as {"status": "error", ...}.
    on_pulled: optional callback run after a pull (use init_db to apply migrations).
    timeout: per-request seconds; pass a small value for startup/close so an unreachable
    server fails fast instead of hanging the UI."""
    cfg = load_config(config_path)
    if not cfg["url"]:
        return {"status": "disabled", "detail": "no sync server configured"}
    try:
        remote = _get_meta(cfg, timeout)
        side = _load_sidecar(db_path)
        local_exists = os.path.exists(db_path)
        local_sha = _sha256_file(db_path) if local_exists else ""
        local_mtime = os.path.getmtime(db_path) if local_exists else time.time()

        remote_version = int(remote.get("version", 0))
        remote_updated = float(remote.get("updated_at", 0.0))

        # 1) server is empty → seed it from local (or nothing to do)
        if remote_version == 0:
            if local_exists:
                return _push(cfg, db_path, local_mtime, timeout=timeout)
            return {"status": "in-sync", "detail": "nothing to sync yet"}

        # 2) never synced on this device but server has data → adopt server (safe onboarding)
        if side["synced_version"] == 0 and not side["local_clean_sha"]:
            if local_exists and local_sha:
                _backup(db_path)
            return _pull(cfg, db_path, on_pulled, timeout=timeout)

        local_changed = local_exists and local_sha != side["local_clean_sha"]
        remote_changed = remote_version != side["synced_version"]

        if not local_changed and not remote_changed:
            return {"status": "in-sync", "detail": "v%s" % remote_version}
        if local_changed and not remote_changed:
            return _push(cfg, db_path, local_mtime, timeout=timeout)
        if remote_changed and not local_changed:
            return _pull(cfg, db_path, on_pulled, timeout=timeout)
        # 3) both changed → last-write-wins by content timestamp; back up the loser
        if local_mtime >= remote_updated:
            return _push(cfg, db_path, local_mtime, conflict=True, timeout=timeout)
        _backup(db_path)
        res = _pull(cfg, db_path, on_pulled, timeout=timeout)
        return {"status": "pulled-conflict", "detail": "remote newer; local backed up (%s)" % res["detail"]}
    except SyncError as e:
        return {"status": "error", "detail": str(e)}
    except Exception as e:  # never let sync crash the app
        return {"status": "error", "detail": "unexpected: %s" % e}
