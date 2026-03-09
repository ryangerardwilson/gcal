# AGENTS.md

## Mission
Implement a small multi-preset Google Calendar CLI for creating, listing, deleting, and rescheduling events.

## Product boundaries
- Scope is Google Calendar event management only.
- The app should stay small and task-focused.
- Primary happy path is creating a calendar event with attendees and a Google Meet link.
- Multi-account support is required through numeric presets.

## Interface constraints
- No-arg invocation prints the same help as `-h`.
- `auth <client_secret_path>` is the standard account bootstrap command.
- Preset-scoped commands:
  - `python main.py <preset> "<title>" "<start>" "<end>" "<invitees_csv>"`
  - `python main.py <preset> ls <count>`
  - `python main.py <preset> d <event_id>`
  - `python main.py <preset> r <event_id> "<start>" "<end>"`
- Keep output plain-text, deterministic, and easy to scan.

## Architecture expectations
- Keep CLI parsing in the entrypoint.
- Keep config, auth, and Calendar API helpers separate.
- Config must be XDG-compliant.
- OAuth tokens must live under `~/.local/share/gcal/tokens/<email>.json` or `$XDG_DATA_HOME/gcal/tokens/<email>.json`.
- Config must persist a timezone string under `defaults.timezone`.
- Event create/list/reschedule must interpret CLI timestamps using that configured timezone.

## Implementation rules
- Python 3.11+.
- Use the Google Calendar API and installed-app OAuth flow.
- Create events on the primary calendar.
- Event creation must request a Google Meet link and send attendee invites.
- Reschedule should preserve the event and update only its times.
- Delete should send attendee updates.

## Done when
- A user can auth one or more presets.
- A user can create an event with attendees and receive a Meet link.
- `ls` shows upcoming events with event id, time, and Meet URL.
- A user can delete and reschedule an event by event id.
- Config and token paths are XDG-compliant.
