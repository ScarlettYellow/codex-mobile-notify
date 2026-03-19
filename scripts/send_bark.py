#!/usr/bin/env python3
"""Send a Bark push notification without third-party dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_BASE_URL = "https://api.day.app"
DEFAULT_GROUP = "Codex"
TIMEOUT_SECONDS = 15
DEFAULT_DEDUPE_WINDOW_SECONDS = 180
DEFAULT_STATE_DIR = "~/.codex/state/codex-mobile-notify"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a Bark push notification for a Codex task."
    )
    parser.add_argument(
        "--event",
        required=True,
        choices=("complete", "action-needed"),
        help="Notification event type.",
    )
    parser.add_argument(
        "--once-key",
        help="Optional task-scoped id used to suppress duplicate notifications for one turn.",
    )
    parser.add_argument("--title", required=True, help="Push title.")
    parser.add_argument("--body", required=True, help="Push body.")
    parser.add_argument(
        "--dedupe-window-seconds",
        type=int,
        default=DEFAULT_DEDUPE_WINDOW_SECONDS,
        help="Skip repeated identical notifications within this many seconds.",
    )
    return parser.parse_args()


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(
            f"Missing required environment variable: {name}. "
            f"Set {name} before using codex-mobile-notify."
        )
    return value


def optional_env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def normalize_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("Title and body must not be empty.")
    return normalized


def get_state_dir() -> Path:
    configured = optional_env("BARK_STATE_DIR") or DEFAULT_STATE_DIR
    return Path(configured).expanduser()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def dedupe_key(args: argparse.Namespace) -> str:
    if args.once_key:
        return f"once:{args.once_key}"
    return "msg:" + sha256_text(f"{args.event}\n{args.title}\n{args.body}")


def should_skip_notification(args: argparse.Namespace) -> tuple[bool, str | None]:
    state_dir = get_state_dir()
    key = dedupe_key(args)
    record_path = state_dir / f"{sha256_text(key)}.json"
    now = int(time.time())
    record = load_json(record_path)

    if args.once_key:
        if record is not None:
            previous_event = record.get("event")
            if isinstance(previous_event, str):
                return True, (
                    f"already sent '{previous_event}' for once-key '{args.once_key}'"
                )
        return False, None

    if record is None:
        return False, None

    sent_at = record.get("sent_at")
    if not isinstance(sent_at, int):
        return False, None
    if args.dedupe_window_seconds < 0:
        return False, None
    if now - sent_at <= args.dedupe_window_seconds:
        return True, "matching notification already sent recently"
    return False, None


def record_notification(args: argparse.Namespace) -> None:
    state_dir = get_state_dir()
    key = dedupe_key(args)
    record_path = state_dir / f"{sha256_text(key)}.json"
    payload: dict[str, object] = {
        "event": args.event,
        "sent_at": int(time.time()),
    }
    if args.once_key:
        payload["once_key"] = args.once_key
    write_json(record_path, payload)


def build_request_payload(args: argparse.Namespace) -> tuple[str, dict[str, object]]:
    device_key = require_env("BARK_DEVICE_KEY")
    base_url = optional_env("BARK_BASE_URL") or DEFAULT_BASE_URL
    base_url = base_url.rstrip("/")
    if not base_url:
        raise ValueError("BARK_BASE_URL must not be empty when provided.")

    payload: dict[str, object] = {
        "device_key": device_key,
        "title": normalize_text(args.title),
        "body": normalize_text(args.body),
        "group": optional_env("BARK_GROUP") or DEFAULT_GROUP,
    }

    sound = optional_env("BARK_SOUND")
    icon = optional_env("BARK_ICON")
    url = optional_env("BARK_URL")

    if sound:
        payload["sound"] = sound
    if icon:
        payload["icon"] = icon
    if url:
        payload["url"] = url

    endpoint = f"{base_url}/push"
    return endpoint, payload


def send_push(endpoint: str, payload: dict[str, object]) -> dict[str, object]:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=encoded,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "codex-mobile-notify/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read().decode("utf-8", errors="replace")
        status = response.getcode()

    try:
        parsed = json.loads(body) if body else {}
    except json.JSONDecodeError:
        parsed = {"raw": body}

    if status < 200 or status >= 300:
        raise RuntimeError(f"Bark request failed with HTTP {status}: {body}")

    code = parsed.get("code")
    if code not in (None, 200):
        message = parsed.get("message") or parsed.get("msg") or body
        raise RuntimeError(f"Bark request failed with code {code}: {message}")

    return parsed


def main() -> int:
    try:
        args = parse_args()
        skip, reason = should_skip_notification(args)
        if skip:
            print(
                f"Skipped Bark notification for event '{args.event}': {reason}"
            )
            return 0
        endpoint, payload = build_request_payload(args)
        result = send_push(endpoint, payload)
        record_notification(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP error from Bark: {exc.code} {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Network error while sending Bark push: {exc.reason}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive fallback
        print(f"Unexpected Bark error: {exc}", file=sys.stderr)
        return 1

    message = result.get("message") or result.get("msg") or "ok"
    print(
        f"Sent Bark notification for event '{args.event}' via "
        f"{urllib.parse.urlparse(endpoint).netloc}: {message}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
