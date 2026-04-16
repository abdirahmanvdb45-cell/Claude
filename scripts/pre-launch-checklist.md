# Pre-Launch Checklist

Complete every item before the first paying client is onboarded.
A checked box means it was tested in staging, not assumed to work.

---

## P0 — Hard Blockers (system cannot launch without these)

- [ ] **Taplio agency/multi-account plan confirmed**
  Single-account design fails at ~3 clients. Verify plan supports all client LinkedIn accounts.

- [ ] **Telegram bot deployed and responding to commands**
  Test: send `/help` → bot replies
  Test: send `/pause test123` → n8n webhook fires, returns response
  Test: send `/status all` → returns client count

- [ ] **Webhook secret set and validated**
  n8n webhook endpoints reject requests without correct `X-Webhook-Secret` header.

- [ ] **2FA enabled on all accounts**
  - [ ] Anthropic (Claude API)
  - [ ] Taplio
  - [ ] Airtable
  - [ ] Google Workspace
  - [ ] Stripe
  - [ ] n8n Cloud
  - [ ] Resend

- [ ] **Privacy Policy live on website**
  Must name all sub-processors: Airtable, Google, Anthropic, Taplio, Stripe, Resend.

---

## Workflow 01 — Monthly Trigger

- [ ] Schedule fires on 1st of month at 9am (test with a manual trigger)
- [ ] Personalised email lands in a test inbox with correct client name and Typeform link
- [ ] Day 4 reminder fires only if no submission received
- [ ] Day 7 reminder fires only if no submission received
- [ ] Day 8 check correctly identifies clients with `last_content_generated` != current month
- [ ] Day 8 check correctly skips clients who have submitted

---

## Workflow 02 — Content Generation

- [ ] Typeform webhook received and `client_id` correctly extracted from hidden field
- [ ] Duplicate submission detection works (submit twice → second is ignored)
- [ ] Voice profile fetched correctly from Airtable
- [ ] Claude API call succeeds and returns posts in `---POST N---` format
- [ ] Validation gate: test with intentionally malformed Claude output → retries, then alerts
- [ ] Validation gate: test with truncated output (short last post) → detected and flagged
- [ ] Google Doc created with correct title, numbered posts, posting times, character counts
- [ ] Google Doc shared as "anyone with link can comment"
- [ ] Delivery email lands in test inbox within **60 seconds** of Typeform submission
- [ ] "Approve & Schedule" button in email links to correct webhook URL with correct params
- [ ] Airtable status updated to `doc_delivered` after delivery
- [ ] Resend fallback (Gmail) activates when Resend credential is intentionally broken

---

## Workflow 03 — Approval & Scheduling

- [ ] Approval webhook fires when button is clicked
- [ ] Duplicate approval (double click) is handled gracefully — second click does nothing
- [ ] Final post text fetched from Google Doc (not from the original Claude output)
- [ ] Pre-flight checks: test each of the 6 checks individually
  - [ ] Placeholder `[NAME]` → blocked
  - [ ] Post > 3,000 chars → blocked
  - [ ] Profanity term → blocked
  - [ ] Empty post → blocked
  - [ ] Duplicate post (same hash) → blocked
  - [ ] Full name that is not the client's → flagged but not blocked
- [ ] Blocked post: only that post skipped, rest of batch schedules normally
- [ ] Taplio POST followed by GET verification — confirmed post appears in queue
- [ ] **Simulated silent Taplio failure**: POST returns 200 but GET finds nothing → flagged as `scheduling_partial`, Telegram alert fires, client does NOT receive confirmation email
- [ ] Airtable status set to `scheduled_confirmed` only after all posts verified
- [ ] Confirmation email sent to client only after `scheduled_confirmed`
- [ ] Buffer API fallback credential activates when Taplio credential is intentionally broken

---

## Workflow 04 — Revision Polling

- [ ] Polling fires every 2 hours between 8am and 10pm
- [ ] Only picks up comments newer than `last_checked_time`
- [ ] Revision correctly replaces only the affected post's text in the doc
- [ ] Comment receives a reply from Claude (not resolved — stays open)
- [ ] Telegram alert fired after each revision
- [ ] Second revision on same comment: works, `pass_number` = 2
- [ ] Third revision attempt on same comment: Claude does NOT run → Telegram escalation alert
- [ ] `last_checked_time` updated after each poll cycle

---

## Workflow 05 — Fallback Generation

- [ ] Day 8 trigger correctly identifies clients who missed the deadline
- [ ] Fallback posts all begin with `[FALLBACK]` label
- [ ] Fallback doc title includes `[FALLBACK]` tag
- [ ] Fallback delivery email includes explicit notice about missing questionnaire
- [ ] Topics used in fallback appended to `past_topics_covered` in Airtable
- [ ] Same GO approval mechanic required — fallback content cannot auto-publish

---

## Workflow 06 — Emergency Control

- [ ] `/pause {client_id}` atomically completes all 3 steps:
  - [ ] Airtable status → `paused_emergency`
  - [ ] Taplio queue cleared
  - [ ] Client notified by email
- [ ] `/pause` partial failure: if any step fails, Telegram reports which steps succeeded and which failed
- [ ] `/resume {client_id}` sets status to `active` and confirms
- [ ] `/pauseall confirm` pauses all clients and clears all queues
- [ ] `/status {client_id}` returns correct current status
- [ ] `/status all` returns accurate counts per status

---

## Security

- [ ] All API keys stored in n8n credentials vault (not env variables for critical keys)
- [ ] Stripe restricted key — read-only, no write permissions
- [ ] Staging environment completely separate from production (different Airtable base, Stripe test mode)
- [ ] No live client data used in any test

---

## Data and Compliance

- [ ] Right-to-erasure workflow tested: cancel a test client → all records deleted at Day 60
- [ ] DPAs signed with: Airtable, Google, Anthropic, Taplio, Stripe, Resend
- [ ] Data retention policy documented and implemented (duration + 60 days post-cancellation)

---

## Final Gate

- [ ] Full end-to-end test with a real test client account:
  - Submit Typeform → receive email in < 60 seconds → approve → posts appear in Taplio queue → verified `scheduled_confirmed` in Airtable
- [ ] Operator can pause and resume via Telegram in under 60 seconds
- [ ] All n8n executions green (no red nodes) on the test run
