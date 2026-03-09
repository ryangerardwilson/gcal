# gcal

Google Calendar CLI for creating, listing, deleting, and rescheduling events across multiple Google account presets.

## Install

Binary install:

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/gcal/main/install.sh | bash
```

Source install:

```bash
cd ~/Apps/gcal
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py -h
```

Flags:
- `-h` prints help
- `-v` prints the current app version
- `-u` upgrades only if a newer release is available

## Google OAuth setup

1. Open Google Cloud Console.
2. Create or select a project.
3. Enable the Google Calendar API.
4. Configure the OAuth consent screen.
5. Create an `OAuth client ID` with application type `Desktop app`.
6. Download the client JSON.

First auth:

```bash
python main.py auth /path/to/client_secret.json
```

The auth flow:
- opens browser OAuth
- discovers the authorized Google account email
- prompts for the calendar timezone
- creates or updates the matching preset in config

## Config

- Config: `~/.config/gcal/config.json`
- Data: `~/.local/share/gcal/`
- OAuth token: `~/.local/share/gcal/tokens/<email>.json`

Example config:

```json
{
  "accounts": {
    "1": {
      "email": "you@example.com",
      "client_secret_file": "/home/ryan/Documents/credentials/client_secret.json"
    }
  },
  "defaults": {
    "timezone": "Asia/Kolkata"
  }
}
```

Notes:
- `defaults.timezone` must be an IANA timezone string like `Asia/Kolkata` or `America/Los_Angeles`.
- CLI timestamps are interpreted in that configured timezone.
- Event creation requests a Google Meet link and sends attendee invites by email.

## Usage

```bash
gcal
gcal -h
gcal -v
gcal -u
gcal auth <client_secret_path>
gcal <preset> "<title>" "<start>" "<end>" "<invitees_csv>"
gcal <preset> ls <count>
gcal <preset> d <event_id>
gcal <preset> r <event_id> "<start>" "<end>"
```

Behavior notes:
- Running `gcal` with no arguments prints the same help as `gcal -h`.
- `gcal auth <client_secret_path>` completes OAuth, discovers the authorized account email, stores the token under the XDG data path, and prints the assigned preset.
- `gcal -u` delegates to the installer and exits without reinstalling when the latest release is already installed.

Examples:

```bash
python main.py auth ~/Documents/credentials/client_secret.json
python main.py 1 "1:1 with Silvia" "2026-03-10 14:00:00" "2026-03-10 15:00:00" "silvia@example.com"
python main.py 1 "Hiring screen" "2026-03-11 10:00:00" "2026-03-11 10:45:00" "a@example.com,b@example.com"
python main.py 1 ls 5
python main.py 1 d abc123def456
python main.py 1 r abc123def456 "2026-03-12 11:00:00" "2026-03-12 11:45:00"
```

Output notes:
- Create prints `event_id` and the Google Meet URL.
- `ls` prints `event_id`, title, formatted time, and Meet URL.
- Delete prints the removed `event_id`.
- Reschedule prints the `event_id` and current Meet URL.

## External dependencies

- Google Calendar API enabled on the OAuth project

## Manual test checklist

1. Run `python main.py auth /path/to/client_secret.json`.
2. Create a test event with one attendee.
3. Confirm the attendee receives the invite email.
4. Confirm the returned Meet URL opens correctly.
5. Run `python main.py 1 ls 5` and verify the event appears with the same URL and time.
6. Reschedule the event and verify the time changes.
7. Delete the event and verify it disappears from Google Calendar.
