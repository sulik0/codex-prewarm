#!/usr/bin/env python3
"""Bounded subscription prewarm; official CLI only, no credential copies."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
CONFIG = json.loads((CONFIG_PATH if CONFIG_PATH.exists() else BASE / "config.example.json").read_text())
CONFIG.setdefault("codex", shutil.which("codex") or "codex")
CONFIG.setdefault("codex_home", str(Path.home() / ".codex"))
CONFIG.setdefault("account_fingerprint", "")
ZONE = ZoneInfo(CONFIG["timezone"])
ENV = dict(os.environ)
ENV["PATH"] = CONFIG.get("child_path", "/opt/homebrew/opt/node@20/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
ENV["CODEX_HOME"] = CONFIG["codex_home"]
# These are agent-session plumbing, not the user's subscription configuration.
for key in ("CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_CLI_PATH",
            "CODEX_APP_TOOLS_PIPE_PATH", "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
            "OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE"):
    ENV.pop(key, None)


class Failure(Exception):
    pass


def now():
    return dt.datetime.now(ZONE)


def stamp(epoch):
    return dt.datetime.fromtimestamp(epoch, ZONE).isoformat(timespec="seconds")


def save(name, value):
    target = BASE / name
    with tempfile.NamedTemporaryFile("w", dir=BASE, delete=False) as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")
        temporary = Path(file.name)
    os.replace(temporary, target)


def load(name):
    path = BASE / name
    return json.loads(path.read_text()) if path.exists() else {}


def record(status, **fields):
    result = {"checked_at": now().isoformat(timespec="seconds"),
              "status": status, **fields}
    save("status.json", result)
    logging.info("%s %s", status, json.dumps(fields, ensure_ascii=False))
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def check_identity():
    try:
        auth = json.loads((Path(CONFIG["codex_home"]) / "auth.json").read_text())
        account_id = (auth.get("tokens") or {}).get("account_id", "")
        fingerprint = hashlib.sha256(account_id.encode()).hexdigest()
        if not account_id or fingerprint != CONFIG["account_fingerprint"]:
            raise Failure("account_changed; re-confirm account before editing config")
        if auth.get("OPENAI_API_KEY") or not auth.get("tokens"):
            raise Failure("subscription_login_required")
    except (OSError, ValueError, KeyError):
        raise Failure("subscription_auth_unreadable") from None


class Server:
    """No threads, no shell, no raw RPC/token data logged."""
    def __enter__(self):
        self.process = subprocess.Popen(
            [CONFIG["codex"], "app-server", "--stdio"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0, env=ENV, cwd=BASE)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer = b""
        self.sequence = 0
        try:
            self.call("initialize", {"clientInfo": {
                "name": "codex_prewarm", "title": "Codex Prewarm", "version": "1.0.0"}})
            self.send({"method": "initialized", "params": {}})
            account = self.call("account/read", {"refreshToken": False}).get("account") or {}
            if account.get("type") != "chatgpt":
                raise Failure("subscription_login_required")
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def send(self, message):
        try:
            self.process.stdin.write((json.dumps(message) + "\n").encode())
            self.process.stdin.flush()
        except (OSError, BrokenPipeError):
            raise Failure("cli_rpc_disconnected") from None

    def call(self, method, params=None):
        self.sequence += 1
        request = {"id": self.sequence, "method": method}
        if params is not None:
            request["params"] = params
        self.send(request)
        end = time.monotonic() + 40
        while time.monotonic() < end:
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                try:
                    reply = json.loads(line)
                except ValueError:
                    continue
                if reply.get("id") == self.sequence:
                    if "error" in reply:
                        raise Failure("cli_rpc_error_%s" % reply["error"].get("code"))
                    return reply["result"]
            if self.selector.select(max(0, end - time.monotonic())):
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise Failure("cli_rpc_closed")
                self.buffer += chunk
        raise Failure("quota_query_timeout")

    def snapshot(self):
        response = self.call("account/rateLimits/read")
        buckets = response.get("rateLimitsByLimitId") or {}
        bucket = buckets.get("codex") or response.get("rateLimits") or {}
        if bucket.get("limitId") not in (None, "codex"):
            raise Failure("target_bucket_missing")
        windows = [bucket.get("primary"), bucket.get("secondary")]
        windows = [window for window in windows if isinstance(window, dict)]
        short = next((w for w in windows if w.get("windowDurationMins") == 300), None)
        weekly = next((w for w in windows if w.get("windowDurationMins") == 10080), None)
        if not short or not short.get("resetsAt"):
            raise Failure("five_hour_window_missing")
        for window in windows:
            value = float(window["usedPercent"])
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise Failure("invalid_quota_value")
        return {"observed_at": time.time(), "reset": float(short["resetsAt"]),
                "used": float(short["usedPercent"]),
                "weekly_used": float(weekly["usedPercent"]) if weekly else None}

    def __exit__(self, *args):
        self.selector.close()
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.process.stdin.close()
        self.process.stdout.close()


def window_state(first, second=None):
    """Idle reset projections move with now. A valid active reset stays fixed."""
    remaining = first["reset"] - first["observed_at"]
    if remaining <= 0:
        return "expired"
    if remaining < 18000 - 90:
        return "active"
    if second is None:
        return "uncertain"
    elapsed = second["observed_at"] - first["observed_at"]
    movement = second["reset"] - first["reset"]
    if abs(movement) <= 2 and second["reset"] > second["observed_at"]:
        return "active"
    if elapsed >= 10 and movement >= 6 and abs(movement - elapsed) <= 5:
        return "idle"
    return "uncertain"


def stable_new_window(before, first, second, sent_at, finished_at):
    reset = second["reset"]
    return (abs(reset - first["reset"]) <= 2
            and reset > second["observed_at"]
            and reset >= sent_at + 18000 - 90
            and reset <= finished_at + 18000 + 90
            and (before.get("window_state") == "idle" or before["reset"] <= sent_at
                 or abs(reset - before["reset"]) > 2))


def read_quota():
    for attempt in range(3):
        try:
            with Server() as server:
                first = server.snapshot()
                if window_state(first) == "uncertain":
                    time.sleep(15)
                    second = server.snapshot()
                    return second, window_state(first, second)
                return first, window_state(first)
        except (Failure, OSError) as error:
            if attempt == 2:
                detail = str(error) if isinstance(error, Failure) else type(error).__name__
                raise Failure("quota_unavailable; " + detail) from None
            time.sleep(10 * (attempt + 1))


def summary(snapshot):
    return {"reset_at": stamp(snapshot["reset"]), "used_percent": snapshot["used"],
            "weekly_used_percent": snapshot["weekly_used"]}


def slot_at(current):
    for value in CONFIG["times"]:
        hour, minute = map(int, value.split(":"))
        target = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
        age = (current - target).total_seconds()
        if 0 <= age <= CONFIG["catchup_minutes"] * 60:
            return current.date().isoformat() + " " + value
    return None


def send_request():
    with tempfile.TemporaryDirectory(prefix="codex-prewarm-") as workspace:
        command = [CONFIG["codex"], "exec", "--ignore-user-config", "--ephemeral",
                   "--skip-git-repo-check", "--sandbox", "read-only",
                   "--model", CONFIG["model"], "-c", 'model_reasoning_effort="low"',
                   "-c", 'approval_policy="never"', "--json", "--cd", workspace,
                   "Reply with exactly OK. Do not use tools or inspect files."]
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, env=ENV, timeout=120)
        except subprocess.TimeoutExpired:
            raise Failure("model_request_timeout; delivery unknown, no automatic resend") from None
        completed = None
        failure_category = "unspecified"
        for line in result.stdout.splitlines():
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if item.get("type") == "turn.completed":
                completed = item.get("usage", {})
            elif item.get("type") in ("error", "turn.failed"):
                # Classify known errors without recording arbitrary server text.
                message = str(item.get("message") or (item.get("error") or {}).get("message", "")).lower()
                if "model" in message and ("not supported" in message or "not found" in message):
                    failure_category = "model_not_supported"
                elif "unauthorized" in message or "authentication" in message:
                    failure_category = "authentication_failed"
                elif "timed out" in message and failure_category == "unspecified":
                    failure_category = "request_timed_out"
        if result.returncode != 0 or completed is None:
            raise Failure("model_request_failed; " + failure_category
                          + "; delivery unknown, no automatic resend")
        return {k: completed.get(k) for k in ("input_tokens", "output_tokens", "cached_input_tokens")}


def run(args):
    slot = slot_at(now()) if args.scheduled else None
    if args.scheduled and slot is None:
        record("outside_schedule", reason="missed slot by more than 30 minutes")
        return 0
    check_identity()
    before, kind = read_quota()
    before["window_state"] = kind
    if args.probe:
        record("probe_" + kind, **summary(before))
        return 0
    state = load("state.json")
    if slot and state.get("last_slot") == slot:
        record("duplicate_slot_skipped", slot=slot, **summary(before))
        return 0
    if not args.test_send and kind == "active":
        record("existing_window", slot=slot, **summary(before))
        return 0
    if not args.test_send and kind == "uncertain":
        raise Failure("idle_state_unconfirmed; request skipped")
    if before["weekly_used"] is None:
        raise Failure("weekly_quota_unknown; request skipped")
    if before["weekly_used"] >= 100 or (kind == "active" and before["used"] >= 100):
        record("quota_exhausted", slot=slot, **summary(before))
        return 0
    sent_at = time.time()
    # Persist BEFORE sending: a crash/timeout must not create an unlimited retry loop.
    if slot:
        save("state.json", {"last_slot": slot, "attempted_at": stamp(sent_at)})
    tokens = send_request()
    finished_at = time.time()
    if kind == "active":
        after, _ = read_quota()
        record("delivery_verified_existing_window", slot=slot, model=CONFIG["model"],
               usage=tokens, **summary(after))
        return 0
    # Two live samples must agree. Never infer success from CLI exit or 0% used.
    for attempt in range(3):
        try:
            with Server() as server:
                first = server.snapshot()
                time.sleep(15)
                second = server.snapshot()
            if stable_new_window(before, first, second, sent_at, finished_at):
                record("new_window_verified", slot=slot, model=CONFIG["model"],
                       usage=tokens, **summary(second))
                return 0
        except (Failure, OSError):
            pass
        if attempt < 2:
            time.sleep(15)
    record("request_completed_window_unverified", slot=slot, model=CONFIG["model"], usage=tokens)
    return 2


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--scheduled", action="store_true")
    modes.add_argument("--probe", action="store_true", help="Read quota; no model request")
    modes.add_argument("--test-send", action="store_true", help="One request even in active window")
    args = parser.parse_args()
    os.umask(0o077)
    lock = (BASE / "run.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('{"status":"already_running"}')
        return 0
    handler = RotatingFileHandler(BASE / "prewarm.log", maxBytes=131072, backupCount=2)
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    def deadline(signum, frame):
        raise Failure("run_deadline_exceeded")
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(480)
    try:
        return run(args)
    except Failure as error:
        record("failed", reason=str(error))
        return 1
    except Exception as error:
        record("failed", reason="unexpected_" + type(error).__name__)
        return 1
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())
