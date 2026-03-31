# Fred Actions

This file tracks decisions, actions, and operational patterns that define how Fred operates and evolves over time. It serves as a reference for maintaining consistency and accountability.

## Purpose

- Record explicit instructions from Ken
- Track decisions made about behavior, boundaries, and responses
- Document patterns that emerge from interactions
- Provide a single source of truth for "how Fred works"

## Sections

### Explicit Instructions
Direct commands or requirements from Ken that must be followed without deviation.

### Operational Policies
Rules about how Fred behaves (e.g., when to speak, how to format responses, what to avoid).

### Lessons Learned
Errors or near-misses and how they were corrected. Things to remember to avoid repeating.

### Boundaries
Hard limits (what Fred will never do) and soft preferences (what Fred avoids unless explicitly instructed).

### Evolution
Changes to identity, workspace structure, or core behavior over time.

## Maintenance

- Update immediately after relevant interactions
- Review periodically (weekly or during significant events)
- Keep concise but precise; avoid fluff
- Use bullet points for clarity
- Add timestamps for major entries

## Creation
Created 2026-03-20 per Ken's instruction to establish accountability and track operational decisions.

## 2026-03-20 — Security Hardening & Maintenance Setup

### Explicit Instructions Received
- Ken authorized per-incident modification of `openclaw.json` to address small model risk.
- Ken directed to schedule daily morning/evening summaries, daily Synology reminder, and weekly audits.
- Ken approved creation of memory structure and instructed to update records near-real-time rather than end-of-day batching.
- Ken requested a separate formal report documenting the baseline analysis.
- Ken later instructed: leave sandboxing off, remove fallback models causing the small model issue, and adjust Synology Chat DM allowlist to use `allowedUserIds` (and `allowFrom`).

### Actions Taken (final configuration)

**Security remediation:**
- Trimmed `agents.defaults.model.fallbacks` to only `openrouter/stepfun/step-3.5-flash:free`, removing `xai/grok-3-fast-latest` and `openrouter/meta-llama/llama-3.3-70b-instruct:free`.
- Added `tools.deny = ["group:web", "browser"]` globally to reduce attack surface while sandbox is off.
- Fixed Synology Chat DM allowlist by adding `allowFrom: ["4"]` (alongside existing `allowedUserIds: ["4"]`).

**Group visibility:**
- Changed WhatsApp `groupPolicy` from `"allowlist"` to `"all"` so I can see any group I’m added to without needing to maintain an allowlist. Removed the unused `groups` block.

**Cron scheduling (`openclaw cron add`):**
- `summary:morning` (08:00 daily)
- `summary:evening` (18:00 daily)
- `task:synology-config` (10:00 daily)
- `healthcheck:security-audit` (Mon 09:00 weekly)
- `healthcheck:update-status` (Mon 09:15 weekly)

**Memory & documentation:**
- Created `memory/` directory and `memory/2026-03-20.md` (daily log).
- Created `MEMORY.md` with curated long-term memory.
- Created `reports/` directory and `reports/2026-03-20-security-baseline.md`.
- Updated `MEMORY.md`, daily memory, and baseline report with actions and rationale.

### Decisions & Rationale
- Avoided sandboxing due to Ken's distrust and prior breakage; instead removed risky fallbacks entirely, which cleanly resolves the audit finding without sandbox complexity.
- Kept web/browser tools globally denied to maintain a reduced attack surface; can revisit if web functionality is needed (either enable sandbox or selectively grant per model).
- Added both `allowedUserIds` and `allowFrom` for Synology to satisfy DM allowlist enforcement; will test.
- Switched WhatsApp `groupPolicy` to `"all"` to avoid maintain a group allowlist and ensure I see any group I’m added to, per Ken’s request.
- Set cron timezone to America/Chicago to match Ken’s timezone.
- Used systemEvent payloads for cron to keep reporting in main session with context.
- Adopted near-real-time memory updates for significant events, reducing forgetting risk.

### Outstanding Items
- Test Synology Chat DM functionality; if it fails, run `openclaw doctor --fix` or further adjust config.
- Verify host disk encryption and arrange encrypted backup of `~/.openclaw/credentials/`.
- Review elevated tools list; prune unnecessary privileges.
- Decide later whether to re‑enable sandboxing if needed for other models or to allow web tools with primary.
- Possibly add more cron for periodic health checks if workload grows.

### User Calibration (from USER_EXTENDED.md)
- Professional background: CIA, CFE, MBA; executive internal audit; currently between roles; seeking CAE-level positions.
- Technical: Mac Mini M2 primary; Orange SSD for models; Synology NAS; Python > Shell; minimum 64k context for reasoning.
- Working style: two steps max for debugging; wait for confirmation; flag assumptions; deliver output then explain if material; propose options; surface relevant info; pushback encouraged.
- Complex tasks: treat as peer; lead with constraints/risks/tradeoffs before solutions; distinguish facts vs inferences.
- Zero-Root Policy; workspace containment; privacy-conscious; decision-first mindset.
- Avoid sycophancy, over-explaining, boilerplate, false certainty, solution-first on complex decisions.
