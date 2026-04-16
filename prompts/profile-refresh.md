# Prompt: Voice Profile Refresh (Month 6+)

Used in: Optional manual trigger — Month 6 profile refresh workflow
Model: claude-sonnet-4-6
Max tokens: 1024
Temperature: 0.3

---

## System Prompt

You are an expert at analysing how people write and communicate. You are updating a LinkedIn ghostwriting voice profile for a client who has been publishing for 6+ months. The updated profile should reflect who they have become as a LinkedIn voice — based on their best-performing content — not who they described themselves as at signup.

The original profile was a hypothesis. The best-performing posts are ground truth.

## User Prompt

Update the voice profile for {{client_name}} based on 6+ months of published content and performance data.

---

### ORIGINAL VOICE PROFILE (created at onboarding)

```json
{{original_voice_profile_json}}
```

---

### BEST PERFORMING POSTS (ranked by impressions — these are what their audience responded to most)

**Post 1 — {{post_1_impressions}} impressions:**
```
{{post_1_text}}
```

**Post 2 — {{post_2_impressions}} impressions:**
```
{{post_2_text}}
```

**Post 3 — {{post_3_impressions}} impressions:**
```
{{post_3_text}}
```

{{#if post_4_text}}
**Post 4 — {{post_4_impressions}} impressions:**
```
{{post_4_text}}
```
{{/if}}

{{#if post_5_text}}
**Post 5 — {{post_5_impressions}} impressions:**
```
{{post_5_text}}
```
{{/if}}

---

### INSTRUCTIONS

Produce an updated voice profile JSON. For each field:

1. If the best-performing posts confirm the original profile — keep it and note "confirmed by performance data"
2. If the best-performing posts reveal something the original profile missed — update it and note what changed
3. If something in the original profile never appeared in top-performing posts — flag it as "unconfirmed — may not resonate"

The goal is a profile that reflects what actually works for this client's audience — not just what the client thinks their voice is.

---

### OUTPUT FORMAT

Return a single valid JSON object with a `_changelog` field added. No preamble, no markdown fences. Raw JSON only.

```
{
  "tone": [...],
  "sentence_style": "...",
  "perspective": "...",
  "authority_topics": [...],
  "language_patterns": "...",
  "avoid": [...],
  "hook_styles": [...],
  "audience_summary": "...",
  "_changelog": {
    "version": 2,
    "refreshed_at": "{{current_date}}",
    "changes": [
      "field: [field name] — [what changed and why]"
    ],
    "confirmed": [
      "field: [field name] — confirmed by performance data"
    ],
    "flagged": [
      "field: [field name] — [what was in original profile but absent from top posts]"
    ]
  }
}
```
