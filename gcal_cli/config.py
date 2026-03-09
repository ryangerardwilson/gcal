from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta, timezone as dt_timezone, tzinfo
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ConfigError
from .paths import config_file, ensure_dirs, tokens_dir


@dataclass(slots=True)
class AccountConfig:
    preset: str
    email: str
    client_secret_file: Path


@dataclass(slots=True)
class AppConfig:
    path: Path
    accounts: dict[str, AccountConfig]
    timezone: str


def normalize_account_email(email: str) -> str:
    return email.strip().lower()


def token_file_for_email(email: str) -> Path:
    return tokens_dir() / f"{normalize_account_email(email)}.json"


def resolve_config_path() -> Path:
    return config_file()


OFFSET_PATTERN = re.compile(r"^([+-])(\d{2}):?(\d{2})$")


def normalize_timezone(value: str) -> str:
    stripped = value.strip()
    match = OFFSET_PATTERN.fullmatch(stripped)
    if not match:
        return stripped
    sign, hours_raw, minutes_raw = match.groups()
    hours = int(hours_raw)
    minutes = int(minutes_raw)
    if hours > 23 or minutes > 59:
        raise ValueError("offset out of range")
    return f"{sign}{hours_raw}:{minutes_raw}"


def timezone_info(value: str) -> tzinfo:
    normalized = normalize_timezone(value)
    match = OFFSET_PATTERN.fullmatch(normalized)
    if match:
        sign, hours_raw, minutes_raw = match.groups()
        offset = timedelta(hours=int(hours_raw), minutes=int(minutes_raw))
        if sign == "-":
            offset = -offset
        return dt_timezone(offset)
    return ZoneInfo(normalized)


def validate_timezone(value: Any, config_path: Path) -> str:
    if value is None:
        return "UTC"
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(
            f"Invalid config at {config_path}: defaults.timezone must be a non-empty IANA timezone or UTC offset"
        )
    try:
        timezone = normalize_timezone(value)
        timezone_info(timezone)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ConfigError(
            f"Invalid config at {config_path}: defaults.timezone must be a valid IANA timezone like 'Asia/Kolkata' or UTC offset like '+05:30'"
        ) from exc
    return timezone


def load_config(path: Path | None = None) -> AppConfig:
    config_path = (path or resolve_config_path()).expanduser()
    ensure_dirs()
    if not config_path.exists():
        raise ConfigError(f"Config not found: {config_path}. Run `gcal auth <client_secret_path>` first.")
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in config {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Invalid config at {config_path}: root must be an object")
    accounts_raw = raw.get("accounts")
    if not isinstance(accounts_raw, dict) or not accounts_raw:
        raise ConfigError(f"Invalid config at {config_path}: 'accounts' must be a non-empty object")
    defaults_raw = raw.get("defaults", {})
    if defaults_raw is None:
        defaults_raw = {}
    if not isinstance(defaults_raw, dict):
        raise ConfigError(f"Invalid config at {config_path}: 'defaults' must be an object")
    timezone = validate_timezone(defaults_raw.get("timezone"), config_path)
    accounts: dict[str, AccountConfig] = {}
    for preset, value in sorted(accounts_raw.items(), key=lambda item: int(item[0])):
        if not isinstance(preset, str) or not preset.isdigit():
            raise ConfigError(f"Invalid config at {config_path}: preset keys must be numeric strings")
        if not isinstance(value, dict):
            raise ConfigError(f"Invalid config at {config_path}: accounts['{preset}'] must be an object")
        email = value.get("email")
        client_secret_file = value.get("client_secret_file")
        if not isinstance(email, str) or not email.strip():
            raise ConfigError(f"Invalid config at {config_path}: accounts['{preset}'].email is required")
        if not isinstance(client_secret_file, str) or not client_secret_file.strip():
            raise ConfigError(f"Invalid config at {config_path}: accounts['{preset}'].client_secret_file is required")
        client_secret_path = Path(client_secret_file).expanduser()
        if not client_secret_path.exists():
            raise ConfigError(
                f"Invalid config at {config_path}: client_secret_file not found for preset '{preset}': {client_secret_path}"
            )
        accounts[preset] = AccountConfig(
            preset=preset,
            email=normalize_account_email(email),
            client_secret_file=client_secret_path,
        )
    return AppConfig(path=config_path, accounts=accounts, timezone=timezone)


def _next_preset(accounts: dict[str, AccountConfig]) -> str:
    numeric_ids = [int(item) for item in accounts]
    return str(max(numeric_ids, default=0) + 1)


def upsert_authenticated_account(
    client_secret_file: Path,
    account_email: str,
    timezone: str,
    path: Path | None = None,
) -> AccountConfig:
    config_path = (path or resolve_config_path()).expanduser()
    ensure_dirs()
    if config_path.exists():
        current = load_config(config_path)
        accounts = dict(current.accounts)
    else:
        accounts = {}
    normalized_email = normalize_account_email(account_email)
    normalized_secret = client_secret_file.expanduser().resolve()
    matched = None
    for account in accounts.values():
        if account.email == normalized_email:
            matched = account
            break
    if matched is None:
        preset = _next_preset(accounts)
        matched = AccountConfig(preset=preset, email=normalized_email, client_secret_file=normalized_secret)
    else:
        matched = AccountConfig(
            preset=matched.preset,
            email=normalized_email,
            client_secret_file=normalized_secret,
        )
    accounts[matched.preset] = matched
    payload = {
        "accounts": {
            preset: {
                "email": account.email,
                "client_secret_file": str(account.client_secret_file),
            }
            for preset, account in sorted(accounts.items(), key=lambda item: int(item[0]))
        },
        "defaults": {
            "timezone": timezone,
        },
    }
    config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return matched


def get_account(config: AppConfig, preset: str) -> AccountConfig:
    if preset not in config.accounts:
        available = ", ".join(sorted(config.accounts)) or "none"
        raise ConfigError(f"Preset `{preset}` not found. Available presets: {available}")
    return config.accounts[preset]
