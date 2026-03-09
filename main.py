from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

from _version import __version__
from gcal_cli.config import get_account, load_config, timezone_info, upsert_authenticated_account, validate_timezone
from gcal_cli.errors import ApiError, ConfigError, GcalError, UsageError

ANSI_RESET = "\033[0m"
ANSI_GRAY = "\033[38;5;245m"


def _muted_text(text: str) -> str:
    if not sys.stdout.isatty() or "NO_COLOR" in os.environ:
        return text
    return f"{ANSI_GRAY}{text}{ANSI_RESET}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gcal", add_help=False)
    parser.add_argument("-h", action="store_true", dest="help")
    parser.add_argument("-v", action="store_true", dest="version")
    parser.add_argument("-u", action="store_true", dest="upgrade")
    parser.add_argument("preset", nargs="?")
    parser.add_argument("command", nargs="?")
    parser.add_argument("params", nargs=argparse.REMAINDER)
    return parser


def _print_help() -> None:
    lines = [
        "Google Calendar event CLI",
        "",
        "flags:",
        "  gcal -h",
        "    show this help",
        "  gcal -v",
        "    print the installed version",
        "  gcal -u",
        "    upgrade to the latest release",
        "",
        "commands:",
        "  gcal auth <client_secret_path>",
        "    authorize a Google account and save or refresh its preset",
        '  gcal <preset> "<title>" "<start>" "<end>" "<invitees_csv>"',
        "    create an event, invite attendees, and request a Google Meet link",
        "  gcal <preset> ls <count>",
        "    list upcoming events",
        "  gcal <preset> ls -nr <count>",
        "    list only non-recurring upcoming events",
        "  gcal <preset> d <event_id>",
        "    delete an event and notify attendees",
        '  gcal <preset> r <event_id> "<start>" "<end>"',
        "    reschedule an existing event",
        "",
        "examples:",
        "  # Auth",
        "  gcal auth ~/Documents/credentials/client_secret.json",
        "",
        "  # Create events",
        '  gcal 1 "Interview" "2026-03-10 14:00:00" "2026-03-10 15:00:00" "a@x.com,b@y.com"',
        "",
        "  # List events",
        "  gcal 1 ls 5",
        "  gcal 1 ls -nr 5",
        "",
        "  # Update events",
        "  gcal 1 d abc123",
        '  gcal 1 r abc123 "2026-03-11 10:00:00" "2026-03-11 11:00:00"',
    ]
    print(_muted_text("\n".join(lines)))


def _parse_time(value: str, timezone: str) -> datetime:
    try:
        naive = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise UsageError("time must use YYYY-MM-DD HH:MM:SS") from exc
    return naive.replace(tzinfo=timezone_info(timezone))


def _parse_invitees(value: str) -> list[str]:
    out = [item.strip() for item in value.split(",") if item.strip()]
    if not out:
        raise UsageError("invitees_csv must include at least one email")
    return out


def _format_event_time(start_iso: str, end_iso: str, timezone: str) -> str:
    tzinfo = timezone_info(timezone)
    start = datetime.fromisoformat(start_iso).astimezone(tzinfo)
    end = datetime.fromisoformat(end_iso).astimezone(tzinfo)
    return f"{start.strftime('%Y-%m-%d %H:%M:%S')} -> {end.strftime('%Y-%m-%d %H:%M:%S')}"


def _handle_auth(params: list[str]) -> int:
    from gcal_cli.auth import authorize_account

    if len(params) != 1:
        raise UsageError("usage: gcal auth <client_secret_path>")
    client_secret = Path(params[0]).expanduser()
    if not client_secret.exists() or not client_secret.is_file():
        raise UsageError(f"missing client secret file: {client_secret}")
    timezone_value = input("Timezone [UTC, +0530, -0430]: ").strip() or "UTC"
    timezone = validate_timezone(timezone_value, Path("<prompt>"))
    authorized = authorize_account(client_secret)
    account = upsert_authenticated_account(client_secret, authorized.email, timezone)
    print(f"authorized\t{account.preset}\t{account.email}\t{timezone}")
    return 0


def _upgrade_to_latest() -> int:
    curl = shutil.which("curl")
    bash = shutil.which("bash")
    if not curl or not bash:
        raise UsageError("curl and bash are required for -u")
    url = "https://raw.githubusercontent.com/ryangerardwilson/gcal/main/install.sh"
    with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        fetch = subprocess.run([curl, "-fsSL", url, "-o", str(tmp_path)], check=False)
        if fetch.returncode != 0:
            return fetch.returncode
        run = subprocess.run([bash, str(tmp_path), "-u"], check=False)
        return run.returncode
    finally:
        tmp_path.unlink(missing_ok=True)


def _print_events(events, timezone: str) -> int:
    if not events:
        print("no events")
        return 0
    sections: list[str] = []
    labels = ("event_id", "title", "time", "attendees")
    label_width = max(len(label) for label in labels)
    use_color = sys.stdout.isatty() and "NO_COLOR" not in os.environ
    for index, event in enumerate(events, start=1):
        prefix = f"[{index}]"
        header = prefix + ("-" * max(1, 79 - len(prefix)))
        attendees = ",".join(event.attendees) if event.attendees else "-"
        lines = [
            f"{'event_id':<{label_width}} : {event.event_id}",
            f"{'title':<{label_width}} : {event.title}",
            f"{'time':<{label_width}} : {_format_event_time(event.start, event.end, timezone)}",
            f"{'attendees':<{label_width}} : {attendees}",
            event.meeting_url,
        ]
        if use_color:
            lines = [f"{ANSI_GRAY}{line}{ANSI_RESET}" for line in lines]
        sections.append("\n".join([header, *lines]))
    print("\n".join(sections))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        _print_help()
        return 0
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.help:
        _print_help()
        return 0
    if args.version:
        print(__version__)
        return 0
    if args.upgrade:
        if args.preset or args.command or args.params:
            raise UsageError("usage: gcal -u")
        return _upgrade_to_latest()
    if args.preset == "auth":
        if args.command is None or args.params:
            raise UsageError("usage: gcal auth <client_secret_path>")
        return _handle_auth([args.command])
    if not args.preset or not args.preset.isdigit():
        raise UsageError("preset must be numeric, like `1` or `2`")
    config = load_config()
    account = get_account(config, args.preset)
    from gcal_cli.auth import build_calendar_service
    from gcal_cli.calendar_api import create_event, delete_event, list_upcoming_events, reschedule_event

    service = build_calendar_service(account)
    if args.command == "ls":
        include_recurring = True
        if args.params[:1] == ["-nr"]:
            include_recurring = False
            params = args.params[1:]
        else:
            params = args.params
        if len(params) != 1:
            raise UsageError("usage: gcal <preset> ls <count>\n       gcal <preset> ls -nr <count>")
        try:
            count = int(params[0])
        except ValueError as exc:
            raise UsageError("count must be a positive integer") from exc
        if count <= 0:
            raise UsageError("count must be > 0")
        return _print_events(
            list_upcoming_events(service, count, include_recurring=include_recurring),
            config.timezone,
        )
    if args.command == "d":
        if len(args.params) != 1:
            raise UsageError("usage: gcal <preset> d <event_id>")
        delete_event(service, args.params[0])
        print(f"deleted\tevent_id={args.params[0]}")
        return 0
    if args.command == "r":
        if len(args.params) != 3:
            raise UsageError('usage: gcal <preset> r <event_id> "<start>" "<end>"')
        start = _parse_time(args.params[1], config.timezone)
        end = _parse_time(args.params[2], config.timezone)
        if end <= start:
            raise UsageError("event end must be after event start")
        event = reschedule_event(service, args.params[0], start, end, config.timezone)
        print(f"rescheduled\tevent_id={event.event_id}")
        print(event.meeting_url)
        return 0
    if args.command is None:
        raise UsageError(
            'usage: gcal <preset> "<title>" "<start>" "<end>" "<invitees_csv>"'
        )
    if len([args.command, *args.params]) != 4:
        raise UsageError(
            'usage: gcal <preset> "<title>" "<start>" "<end>" "<invitees_csv>"'
        )
    title, start_raw, end_raw, invitees_raw = [args.command, *args.params]
    start = _parse_time(start_raw, config.timezone)
    end = _parse_time(end_raw, config.timezone)
    if end <= start:
        raise UsageError("event end must be after event start")
    event = create_event(service, title, start, end, config.timezone, _parse_invitees(invitees_raw))
    print(f"created\tevent_id={event.event_id}")
    print(event.meeting_url)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GcalError as exc:
        print(exc.message, file=sys.stderr)
        raise SystemExit(exc.exit_code)
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        print(f"subprocess failed: {message}", file=sys.stderr)
        raise SystemExit(2)
