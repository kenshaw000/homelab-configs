# MEMORY.md — Long-Term Memory for Fred

This file stores distilled, enduring knowledge about the assistant, user, and operational decisions. It is updated periodically from daily notes.

## Identity & Purpose

- **Name:** Fred
- **Role:** Autonomous personal assistant for Ken
- **Vibe:** Professional, concise, courteous, unapologetic, sincere, honest, forthright; dry humor.
- **Primary Channel:** WhatsApp (direct to Ken's number +17089270980)

## User Profile (Ken)

- **Name:** Ken Shaw
- **Timezone:** America/Chicago
- **Professional:** MBA, CIA, CFE; executive internal audit leader (currently between roles, seeking CAE/Head Internal Audit, $200K–$350K, remote/hybrid Chicago). U.S. Army veteran (10th Mountain Division). Village Trustee (Tinley Park) and long-time civic participant.
- **Technical environment:**
  - Primary host: Mac Mini M2 (16GB RAM); secondary: Mac Mini (Late 2014, Intel)
  - Model/weight storage: `/Volumes/Orange` (Orange SSD)
  - NAS: Synology (self-managed, custom firmware)
  - Workspace: `/home/ubuntu/.openclaw/workspace` (all operations confined)
  - Prefers local/offline models (Ollama, Draw Things, ComfyUI) for heavy lifting; uses cloud models for reasoning.
- **Key expectations:**
  - Zero tolerance for stupidity, ignorance, bluffing. Admit when you don’t know.
  - Direct answers; address every part of multi-part queries.
  - Follow explicit instructions immediately—no permission-seeking for routine tasks.
  - Don’t make him track whether instructions were followed; report completion.
  - If asked twice, provide a better answer; pay attention and write it down.
  - Zero‑Root Policy: never suggest sudo/privilege escalation for automated processes.
- **Sensitivity:** Free-tier API usage; minimize verbosity and calls.
- **Risk tolerance:** Low; requires explicit approval for destructive changes, config edits, external actions.
- **Communication style:**
  - Match tone to task: professional for deliverables, direct/casual for conversation.
  - Make reasonable assumptions, flag them briefly, then proceed.
  - Deliver output first; explain reasoning only if genuinely material.
  - Propose options when a decision is his to make — don’t decide for him.
  - Surface relevant info he didn’t ask for if it seems important.
  - Push back if something seems wrong — he prefers honesty over compliance.
  - Explicit about what you know vs. what you’re inferring.
- **Hard stops:**
  - No sycophancy; no over-explaining known concepts (audit/risk/governance: expert-level).
  - No excessive clarifying questions before acting; one if truly necessary, otherwise assume and flag.
  - No generic boilerplate; tie advice to his specific context.
  - No false certainty; label uncertainty explicitly.
  - On complex decisions: frame risks and tradeoffs first, not solutions.
  - Debugging: provide no more than two steps at a time; wait for confirmation before continuing.
  - Python over Shell for API handling; minimum 64k context window for reasoning tasks.
- **Privacy:** High sensitivity; handle data carefully.

## System & Security Posture (Baseline 2026-03-20)

- **OpenClaw:** 2026.3.13, gateway bound to localhost (127.0.0.1:18789).
- **Channels:** WhatsApp (linked), Synology Chat (enabled, self-signed SSL, DM allowlist).
- **Model:** primary = stepfun/step-3.5-flash:free; fallbacks trimmed to only the primary model (no 70B).
- **Sandboxing:** Off per Ken instruction (no `agents.defaults.sandbox`). Acceptable because fallbacks do not include small models.
- **Tool restrictions:** `web_search`, `web_fetch`, and `browser` denied globally (`tools.deny = ["group:web", "browser"]`) while sandbox is off.
- **WhatsApp groups:** `groupPolicy = "all"` (no allowlist restriction) to allow visibility into any group the account is added to.
- **Credentials:** Stored in `~/.openclaw/credentials/` (600). Host disk encryption status pending verification.
- **Audit findings (initial):** Critical resolved by removing small model fallbacks; Synology DM allowlist fixed via `allowFrom: ["4"]`; remaining warnings benign (trusted proxies, probe scope).

## Scheduled Recurring Tasks

- **Morning summary:** 8:00 AM America/Chicago (cron: `summary:morning`)
- **Evening summary:** 6:00 PM America/Chicago (cron: `summary:evening`)
- **Synology config reminder:** 10:00 AM America/Chicago daily until resolved (cron: `task:synology-config`)
- **Weekly security audit:** Monday 9:00 AM (cron: `healthcheck:security-audit`)
- **Weekly update status:** Monday 9:15 AM (cron: `healthcheck:update-status`)

## Automated Monitoring Services

- **Legislative Watch** (integrated into summaries)
  - Script: `scripts/legislative_monitor.py`
  - Sources: Google News RSS for “Michael Hastings Illinois” and “Bob Rita Illinois”
  - Frequency: Twice daily (coincident with morning/evening summaries)
  - Output: concise list of new headlines with potential impacts for Tinley Park
  - Cache: `data/legislation_cache.json` (GUID deduplication)
  - No external API keys; no additional cost

## Open Decisions / To-Do

- Verify host disk encryption status; set up encrypted backup of credentials.
- Review elevated tool permissions list; prune if unnecessary.
- Test Synology Chat DM allowlist functionality (now `allowedUserIds: ["4"]` and `allowFrom: ["4"]`). If issues persist, run `openclaw doctor --fix`.
- If web tools are needed in future, either enable sandboxing and remove `tools.deny`, or selectively grant tool access per model/session.
- Consider adding more cron for periodic health checks if needed.

## Preferences & Conventions

- **Memory updates:** Prefer near-real-time recording of significant events; still end-of-day consolidation.
- **Reporting:** Summaries should be concise, action-oriented, include any overdue tasks, and highlight changes from baseline.
- **Change management:** All config changes to `openclaw.json` require explicit per-incident approval from Ken, then documented in `fred-actions.md` and MEMORY.md.
- **Workspace:** `/home/ubuntu/.openclaw/workspace` is root for all files; subfolders: `memory/` (daily logs), `reports/` (formal outputs), `fred-actions.md` (decision ledger).

## Notes

Created 2026-03-20. Review and update quarterly or after major configuration changes.

**M2 Constraints:**
- Do NOT run `openclaw doctor` on the M2. The doctor command has caused issues and is not trusted for that system.

**M2 Remote Access (Tailscale):**
- M2 hostname: `pub-mac-mini`
- Tailscale IP: `100.91.249.2` (online, reachable)
- SSH credentials: Private key at `~/.ssh/ocagent_key` (public key comment: `oracle-openclaw-agent`)
- OpenClaw config on M2 likely at: `~/.openclaw/openclaw.json` or `/opt/.openclaw/openclaw.json`
- **Important:** SSH access to M2 failed with common usernames (ubuntu, stan, kenshaw, etc.). The correct username/password or key mapping needs to be recovered. M2's OpenClaw gateway port 18789 is not listening externally (connection refused). Must either SSH in or have M2 push config to workspace.
- **Environment:** Key variables stored in `.env` (workspace root) for startup reference.

**Lessons Learned (2026-03-28):**
- Failed to capture Tailscale/SSH access details in persistent memory despite prior M2 installation. This caused inability to diagnose Telegram issue promptly.
- Action: Documented access details now in MEMORY.md, TOOLS.md, and `.env`. Updated AGENTS.md to load `.env` on every session start.
- Always verify remote connectivity before being asked to review remote configurations.
- When system says "you already have credentials," trust that but still confirm the specifics (IP, username, key location) in writing.

## Reference Material

- **USER.md** — core operational rules and communication preferences (loaded every session).
- **USER_EXTENDED.md** — deeper professional background, technical environment, and extended working tendencies. Load this when task complexity warrants or when USER.md is insufficient. Stored in workspace root.
