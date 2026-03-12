from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

from _version import __version__
from gcal_cli.config import (
    get_account,
    load_config,
    resolve_config_path,
    timezone_info,
    upsert_authenticated_account,
    validate_timezone,
)
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
        "  gcal conf",
        "    open the config in your editor",
        "",
        "features:",
        "  authorize a Google account and save or refresh its preset",
        "  # auth <client_secret_path>",
        "  gcal auth ~/Documents/credentials/client_secret.json",
        "",
        "  create an event, invite attendees, and request a Google Meet link",
        '  # <preset> "<title>" "<start>" "<end>" "<invitees_csv>"',
        '  gcal 1 "Interview" "2026-03-10 14:00:00" "2026-03-10 15:00:00" "a@x.com,b@y.com"',
        "",
        "  list non-recurring events by default, or switch to all / recurring-only",
        "  # <preset> ls <count> | ls -a <count> | ls -r <count> | ls -h <count>",
        "  gcal 1 ls 5",
        "  gcal 1 ls -a 5",
        "  gcal 1 ls -r 5",
        "  gcal 1 ls -h 5",
        "",
        "  export a transcript attachment for a past Google Meet event",
        "  # <preset> tr <event_id>",
        "  gcal 1 tr abc123",
        "",
        "  delete or reschedule an existing event",
        '  # <preset> d <event_id> | r <event_id> "<start>" "<end>"',
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
    if "T" not in start_iso or "T" not in end_iso:
        return f"{start_iso} -> {end_iso}"
    tzinfo = timezone_info(timezone)
    start = datetime.fromisoformat(start_iso).astimezone(tzinfo)
    end = datetime.fromisoformat(end_iso).astimezone(tzinfo)
    return f"{start.strftime('%Y-%m-%d %H:%M:%S')} -> {end.strftime('%Y-%m-%d %H:%M:%S')}"


def _handle_auth(params: list[str]) -> int:
    from gcal_cli.auth import CALENDAR_SCOPES, authorize_account

    if len(params) != 1:
        raise UsageError("usage: gcal auth <client_secret_path>")
    client_secret = Path(params[0]).expanduser()
    if not client_secret.exists() or not client_secret.is_file():
        raise UsageError(f"missing client secret file: {client_secret}")
    timezone_value = input("Timezone [UTC, +0530, -0430]: ").strip() or "UTC"
    timezone = validate_timezone(timezone_value, Path("<prompt>"))
    authorized = authorize_account(client_secret, CALENDAR_SCOPES)
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


def _open_config_in_editor() -> int:
    cfg_path = resolve_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if not cfg_path.exists():
        cfg_path.write_text('{"defaults":{"timezone":"UTC"},"accounts":{}}\n', encoding="utf-8")
    editor = (os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vim").strip()
    editor_cmd = shlex.split(editor) if editor else ["vim"]
    if not editor_cmd:
        editor_cmd = ["vim"]
    return subprocess.run([*editor_cmd, str(cfg_path)], check=False).returncode


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


def _parse_ls_params(params: list[str]) -> tuple[int, str, bool]:
    recurrence_mode = "non_recurring"
    historical = False
    remaining = list(params)
    while remaining and remaining[0].startswith("-"):
        flag = remaining.pop(0)
        if flag == "-a":
            recurrence_mode = "all"
            continue
        if flag == "-r":
            recurrence_mode = "recurring"
            continue
        if flag == "-h":
            historical = True
            continue
        raise UsageError(
            "usage: gcal <preset> ls <count>\n"
            "       gcal <preset> ls -a <count>\n"
            "       gcal <preset> ls -r <count>\n"
            "       gcal <preset> ls -h <count>\n"
            "       gcal <preset> ls -h -a <count>\n"
            "       gcal <preset> ls -h -r <count>"
        )
    if len(remaining) != 1:
        raise UsageError(
            "usage: gcal <preset> ls <count>\n"
            "       gcal <preset> ls -a <count>\n"
            "       gcal <preset> ls -r <count>\n"
            "       gcal <preset> ls -h <count>\n"
            "       gcal <preset> ls -h -a <count>\n"
            "       gcal <preset> ls -h -r <count>"
        )
    try:
        count = int(remaining[0])
    except ValueError as exc:
        raise UsageError("count must be a positive integer") from exc
    if count <= 0:
        raise UsageError("count must be > 0")
    return count, recurrence_mode, historical


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
    if args.preset == "conf":
        if args.command or args.params:
            raise UsageError("usage: gcal conf")
        return _open_config_in_editor()
    if args.preset == "auth":
        if args.command is None or args.params:
            raise UsageError("usage: gcal auth <client_secret_path>")
        return _handle_auth([args.command])
    if not args.preset or not args.preset.isdigit():
        raise UsageError("preset must be numeric, like `1` or `2`")
    config = load_config()
    account = get_account(config, args.preset)
    from gcal_cli.auth import build_calendar_service
    from gcal_cli.calendar_api import create_event, delete_event, get_event, list_historical_events, list_upcoming_events, reschedule_event

    service = build_calendar_service(account)
    if args.command == "ls":
        count, recurrence_mode, historical = _parse_ls_params(args.params)
        events = (
            list_historical_events(service, count, recurrence_mode=recurrence_mode)
            if historical
            else list_upcoming_events(service, count, recurrence_mode=recurrence_mode)
        )
        return _print_events(
            events,
            config.timezone,
        )
    if args.command == "tr":
        if len(args.params) != 1:
            raise UsageError("usage: gcal <preset> tr <event_id>")
        from gcal_cli.auth import build_drive_service
        from gcal_cli.transcripts import export_transcript_text, find_transcript_attachment, save_transcript

        drive_service = build_drive_service(account)
        event = get_event(service, args.params[0])
        attachment = find_transcript_attachment(event)
        text = export_transcript_text(drive_service, attachment.file_id)
        output_path = save_transcript(
            text,
            event_id=str(event.get("id", "")),
            title=str(event.get("summary", "(untitled)")),
            start_value=str(event.get("start", {}).get("dateTime") or event.get("start", {}).get("date", "")),
        )
        print(f"saved transcript\tevent_id={event.get('id', '')}\tfile_id={attachment.file_id}")
        print(output_path)
        return 0
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
