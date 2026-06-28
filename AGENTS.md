# AGENTS.md — Codex handoff for KUS

Last reviewed by Codex: 2026-06-27.

This file is the working memory for Codex in this repo. Keep it current when the
project state, deployment rules, checks, or known risks change. `CLAUDE.md` is
the broader project narrative; this file is the short operational version for
future Codex runs.

## Project

KUS ("Кусь") is a live dog diet service:

- funnel: Telegram bot / landing -> questionnaire -> YooKassa payment -> diet
  calculation and AI text -> HTML report -> specialist review -> delivery;
- natural diet track: `calculator.py` + `pdf_generator.py`;
- dry food track: `dry_food_selector.py`;
- backend/admin/payment: `app.py`;
- Telegram mini-course, support, and Telegram delivery loop: `bot.py`;
- post-payment processing and email/VK delivery: `worker.py`;
- orders DB: `kus.db`; bot/support DB: `bot.db`;
- report artifacts: `output/`;
- templates: `templates/*.html`.

Client-facing positioning is important: do not sell this as "AI/neural network".
Say the report is calculated by veterinary norms and checked by a specialist.
Legal pages may disclose auxiliary automation softly.

## Runtime Topology

- This path, `/mnt/5.42-opt/kus`, is an sshfs mount of production `/opt/kus`
  on Moscow `5.42.101.215`. Edits here are production-file edits.
- Production app service: `kus.service`, uvicorn `app:app` on port `8007`.
- Production bot service: `kus-bot.service`, runs `bot.py`.
- Amsterdam clone/orchestration path referenced by project docs: `/root/kus`.
- Telegram egress from `5.42` is unreliable/unavailable; Telegram sending should
  be done by the bot/orchestration path that can reach `api.telegram.org`.
- Do not trust local `systemctl` on Amsterdam for Moscow service state. Check the
  Moscow host explicitly.

## Safety Rules

- Start read-only. Do not restart services, edit DB/payment state, or send real
  client messages without explicit approval.
- Prefer fixing and testing in the safer clone when available. If working in this
  sshfs mount, remember that code edits touch production files.
- Never mark a paid order as done manually unless the business owner explicitly
  asks and the review/delivery implications are clear.
- Do not expose or print `.env` secrets. Redacted `SET/EMPTY` checks are OK.
- No diet/report consistency bug fix without the ratchet:
  `calculator.py`/`pdf_generator.py` root fix -> invariant in `reconcile.py` ->
  regression profile in `evals.py` -> project gate.
- For generated report changes, update `tools/golden_snapshots.json` only when
  the visual/numeric change is expected and reviewed.

## Core Flow

Order statuses are in `models.ORDER_STATUSES`:

`new -> paid -> processing -> review -> done`, plus `rework` and `error`.

- `app.submit_order`: validates questionnaire, creates order, redirects to
  YooKassa when configured.
- `app.yookassa_webhook`: handles YooKassa callbacks. Current code rechecks the
  payment via YooKassa API in `_verify_yookassa_payment`; the old spoofing risk
  is addressed in code by requiring `status=succeeded`, `paid=true`, and matching
  `metadata.order_id`.
- `worker.process_order`: parses free text, generates natural/dry HTML, saves
  sidecar AI text metadata, runs auto-checks, and sets status to `review`.
- `/admin/review`: specialist reviews. Approve sets `done` and calls
  `worker.deliver_order`; rework regenerates; edit rerenders text without new AI.
- Client report URL `/order/{id}/view` only serves reports with status `done`.
  Admin preview `/admin/order/{id}/view` is protected by Basic auth.

## Checks

Preferred project gate:

```bash
bash tools/check.sh
```

It runs:

```bash
./venv/bin/python tools/canary.py
./venv/bin/python tools/snapshot.py
./venv/bin/python tools/gate_reconcile.py
```

Important current verification note from 2026-06-27: in this Codex environment,
`bash tools/check.sh` failed before business checks because WeasyPrint could not
load system library `libpangoft2-1.0-0`. Run the gate on the production host or
an environment with Pango/WeasyPrint system dependencies installed before treating
the code as locally verified. The same gate was run on `5.42` on 2026-06-27 and
passed: canary OK, golden snapshot OK, reconciliation 17/17 profiles clean.

The currently important reconciliation invariant `Норма = сумма групп` exists in
`reconcile.py` and is covered by `tools/canary.py`.

## Current Config State Observed 2026-06-27

Redacted `.env` inspection showed:

- `BOT_TOKEN`, `ADMIN_TELEGRAM_ID`, `YOOKASSA_SHOP_ID`,
  `YOOKASSA_SECRET_KEY`, `GOOGLE_CLOUD_PROJECT`,
  `GOOGLE_APPLICATION_CREDENTIALS`, `SMTP_HOST`, `SMTP_PORT`, `BASE_URL`,
  `ADMIN_USER` are set.
- `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `GEMINI_API_KEY` are empty.
- `ADMIN_PASS` still equals the known default `kus2026` and must be changed for
  public admin routes.
- `VK_TOKEN` was absent from the redacted check output; verify/add it before
  assuming VK auto-delivery works.

Impact: email delivery and review email notifications are not operational while
SMTP credentials are empty. Vertex/Google credentials may still handle Gemini
even with `GEMINI_API_KEY` empty, depending on `ai_adapter.py`.

## Known Risks / Bugs To Prioritize

1. Public admin password risk: `app.py` defaults `ADMIN_PASS` to `kus2026`, and
   current `.env` inspection showed this default is still in use.
2. Email delivery blocked: `worker.deliver_order` sends email only if
   `SMTP_USER` is set; `SMTP_USER/PASSWORD/FROM` were empty.
3. VK delivery still needs real config: `templates/status.html` now shows a
   first-contact instruction and optional button, but `.env` must provide
   `VK_TOKEN` and ideally `VK_COMMUNITY_URL`.
4. Local verification environment is incomplete: missing `libpangoft2-1.0-0`
   prevents WeasyPrint-based gates in this session, although the gate passed on
   `5.42`.
5. `worker._send_vk_link` uses `random_id=order["id"]`. For combo reports or
   repeated delivery retries with changed text, VK may deduplicate retries. Use
   a more specific id if repeated delivery semantics matter.
6. `bot.py` creates `Bot(token=BOT_TOKEN)` at import time. If `BOT_TOKEN` is
   missing, any import path that touches `bot` can fail early.
7. `app.mount("/preview", StaticFiles(directory=output_dir))` exposes generated
   output artifacts under `/preview`. It may include old/demo/client report HTMLs;
   review whether this route is intended to remain public.
8. Old generated artifacts and DB files live in the repo directory. Be careful
    with git status/cleanup; do not delete production data or reports casually.

## Work Plan

Immediate launch blockers:

1. Change `ADMIN_PASS` and preferably `ADMIN_USER`; restart the relevant service
   after owner approval.
2. Fill `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, and `ADMIN_EMAIL`; send a test
   review notification and test client email delivery.
3. Verify `VK_TOKEN`, set `VK_COMMUNITY_URL`, and test that VK delivery works
   after the user writes to the community first.
4. Run a full end-to-end test order: questionnaire -> YooKassa test payment ->
   `review` -> text edit -> rework -> approve -> delivery channels.
5. After config/restart changes, rerun `bash tools/check.sh` on `5.42`.

Code hardening after blockers:

1. Add a small delivery status panel or admin warning when requested channels are
   impossible because SMTP/VK/TG prerequisites are missing.
2. Add explicit tests for delivery channel selection and "status done only" report
   access.
3. Decide whether `/preview` should be public. If not, protect it or remove the
   mount.
4. Improve VK retry idempotency and log actionable VK errors in admin review.

Quality improvements:

1. Expand dry-food invariants in `tools/report_qa/check_dry.py` as described in
   `tools/report_qa/ROADMAP.md`.
2. Add edge cases for unknown breeds, conflicting health input, pregnancy plus
   lactation, tiny puppies, and dirty stop-product text.
3. Keep `CLAUDE.md`, `PLAN.md`, and this `AGENTS.md` synchronized when tasks are
   completed.
