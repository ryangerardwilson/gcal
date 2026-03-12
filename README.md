# gcal

Google Calendar CLI for creating, listing, deleting, rescheduling, and exporting transcript artifacts for events across multiple Google account presets.

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

`gcal -v` prints the installed app version from `_version.py`. Source
checkouts keep the checked-in placeholder at `0.0.0`; tagged release builds
stamp the shipped artifact with the real version.

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
- `defaults.timezone` may be an IANA timezone string like `Asia/Kolkata` or a UTC offset like `+05:30`.
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
gcal <preset> ls -nr <count>
gcal <preset> ls -h <count>
gcal <preset> d <event_id>
gcal <preset> r <event_id> "<start>" "<end>"
gcal <preset> tr <event_id>
```

Behavior notes:
- Running `gcal` with no arguments prints the same help as `gcal -h`.
- `gcal auth <client_secret_path>` completes OAuth, discovers the authorized account email, stores the token under the XDG data path, and prints the assigned preset.
- During `auth`, you can enter either an IANA timezone like `Asia/Kolkata` or a raw offset like `+0530`.
- `gcal <preset> ls -nr <count>` lists only non-recurring events.
- `gcal <preset> ls -h <count>` lists the most recent historical events, printed oldest-to-newest.
- `gcal <preset> tr <event_id>` exports a Google Meet transcript attachment for that event into `~/.local/share/gcal/transcripts/` when one is available and accessible to the authorized account.
- `gcal -u` delegates to the installer and exits without reinstalling when the latest release is already installed.

Examples:

```bash
python main.py auth ~/Documents/credentials/client_secret.json
python main.py 1 "1:1 with Silvia" "2026-03-10 14:00:00" "2026-03-10 15:00:00" "silvia@example.com"
python main.py 1 "Hiring screen" "2026-03-11 10:00:00" "2026-03-11 10:45:00" "a@example.com,b@example.com"
python main.py 1 ls 5
python main.py 1 ls -nr 5
python main.py 1 ls -h 5
python main.py 1 d abc123def456
python main.py 1 r abc123def456 "2026-03-12 11:00:00" "2026-03-12 11:45:00"
python main.py 1 tr abc123def456
```

Output notes:
- Create prints `event_id` and the Google Meet URL.
- `ls` prints `event_id`, title, formatted time, and Meet URL.
- Delete prints the removed `event_id`.
- Reschedule prints the `event_id` and current Meet URL.

## External dependencies

- Google Calendar API enabled on the OAuth project
- Google Drive API enabled on the OAuth project for transcript exports

## Manual test checklist

1. Run `python main.py auth /path/to/client_secret.json`.
2. Create a test event with one attendee.
3. Confirm the attendee receives the invite email.
4. Confirm the returned Meet URL opens correctly.
5. Run `python main.py 1 ls 5` and verify the event appears with the same URL and time.
6. Run `python main.py 1 ls -h 5` and verify recent past events are shown oldest-to-newest.
7. Run `python main.py 1 tr <event_id>` for a meeting with transcription enabled and verify a text file is written under the XDG data directory.
8. Reschedule the event and verify the time changes.
9. Delete the event and verify it disappears from Google Calendar.
