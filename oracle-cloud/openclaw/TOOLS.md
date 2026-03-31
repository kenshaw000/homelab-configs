# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _yours_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## My SSH Access

- **pub-mac-mini (M2)** → `100.91.249.2` via Tailscale, user unknown (key: `~/.ssh/ocagent_key`, pub: `oracle-openclaw-agent`). Common usernames tried without success. Need to determine correct username or have M2 push config.
- **OpenClaw config path on M2:** likely `~/.openclaw/openclaw.json` or `/opt/.openclaw/openclaw.json`

**Startup check:** Always load `.env` from workspace root for environment variables (M2 IP, SSH key, paths). Update `.env` when any of these change.

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
