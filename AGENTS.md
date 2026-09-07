# AGENTS.md

This file is for any AI coding agent (Claude Code, Copilot, Cursor, etc.) working in this repository. Read this before writing or modifying code. It reflects the current, time-boxed scope, not the full long-term vision in PRD.md/Architecture.md.

## Project
LabelBox: a tool for Legal Metrology enforcement officers to photograph a product label, extract its declarations via OCR, and validate them against the Legal Metrology (Packaged Commodities) Rules, 2011, returning cited violations.

## Current Scope (one-day build — read this first)
This is being built in a single day for a hackathon demo. The only thing cut from the full project docs is the frontend framework: plain HTML/JS instead of React, to avoid build-tooling overhead. Everything else in Architecture.md still applies — do not assume other features are cut unless explicitly told so.

**In scope right now:**
- FastAPI backend with endpoints for scan submission and retrieval
- OCR via EasyOCR
- Regex/heuristic-based field extraction (MRP, net quantity, manufacture date, manufacturer address, consumer care)
- Rule engine checking extracted fields against the Legal Metrology rules, with cited violations
- PostgreSQL on Neon as the database, connection string via `DATABASE_URL`, pooled connection string used
- JWT-based officer authentication/login
- Offline support: service worker + IndexedDB queue for scans submitted without connectivity, auto-retry on reconnect
- Plain HTML/JS frontend (no framework, no bundler) — camera capture, result display, login

**Explicitly out of scope for today — do not build these unless asked:**
- No React or any frontend framework/build step
- No multilingual OCR
- No PDF export
- No historical pattern detection across sessions (repeat offenders)
- No visual bounding-box overlay on images

If time runs out, drop items in this order: bounding-box overlay and pattern detection first (never in scope today anyway), then offline queue, then auth, keeping the core scan → extract → validate → result flow working above everything else.

## Tech Stack
- Backend: Python, FastAPI, SQLAlchemy, JWT auth
- Database: PostgreSQL on Neon (pooled connection string), Alembic for migrations
- OCR: EasyOCR
- Image processing: OpenCV, only if actually needed for preprocessing — don't add it speculatively
- Frontend: plain HTML/JS, no framework, no bundler; service worker + IndexedDB for offline queueing

## Code Style
- Keep functions small and single-purpose, especially rule-check functions — one function per rule, easy to read in isolation
- Type hints on backend function signatures
- No dead code or commented-out blocks
- Minimal comments; skip ones that just restate the code, but do comment non-obvious rule logic (why a check exists, what legal requirement it maps to)

## Error Handling
- Wrap OCR calls and image decoding in try/except; never let a bad image crash the endpoint
- If a field can't be extracted, return it as `null`/`not_found` rather than failing the whole request
- Return structured JSON errors from the API, not raw stack traces

## What NOT to Do
- Do not fabricate legal rule text or citations. If unsure of exact wording, mark it as a placeholder rather than inventing something plausible-sounding.
- Do not introduce a frontend framework or build tooling
- Do not hardcode the Neon connection string or any credentials — always read from `DATABASE_URL`
- Do not silently swallow exceptions
- Do not build multilingual OCR, PDF export, pattern detection, or bounding-box overlays without being asked — these are explicitly deferred

## Maintain memory.md
Keep a file called `memory.md` at the repo root, and update it as you work. This is the running log of what's actually been done, so any agent (or person) picking this up mid-build has real context instead of having to re-read the whole codebase or ask again.

Every time you complete a meaningful chunk of work, append an entry covering:
- What was built or changed
- Any decision made and why, especially if it deviates from these docs
- Any known issue, workaround, or thing left half-done
- What the logical next step is

Format as short dated/timestamped entries, newest at the bottom. Don't rewrite history, don't delete old entries, don't summarize away detail to keep it short, this is a log, not a polished doc. If something in these project docs (PRD.md, Architecture.md, Rules.md, Phases.md) turns out to be wrong or outdated based on what you actually built, note that in memory.md rather than silently ignoring the mismatch.

## Reference Docs (fuller vision, not today's scope)
- `PRD.md` — full target users and feature set
- `Architecture.md` — full target stack (Postgres/Neon, PWA, offline sync)
- `Phases.md` — original 7-phase plan for a multi-day build
- `PROJECT_OVERVIEW.md` — narrative summary of the above

Treat these as where the project is headed after today, not as today's task list.
