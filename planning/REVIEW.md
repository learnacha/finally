# Code Review — Changes Since Last Commit

**Branch:** `start`
**Reviewed:** 2026-05-27

---

## Files Changed

- `.claude/agents/change-reviewer.md` — typo fix + tool swap (`codex exec` → `claude -p`)
- `planning/PLAN.md` — major documentation enrichment: exact model IDs, SSE payload example, LLM actions schema, new Section 13 (Implementation Reference)

---

## Findings

### Strengths

1. **Section 13 (Implementation Reference) is an excellent addition.** It gives all agents one authoritative place to look up confirmed implementation facts, each backed by a GitHub link to the reference branch. This eliminates guesswork and inter-agent inconsistency. High value for a multi-agent project.

2. **Conversation history window is now quantified.** The `load_chat_history(db, limit=20)` callout in Section 13 removes the ambiguity that existed in the earlier plan, where "last N messages" was unspecified.

3. **SSE event payload is now concrete.** The JSON example in Section 6 gives frontend engineers an exact contract to code against, reducing integration bugs.

4. **`watchlist_changes.action` values are now enumerated.** Specifying `"add"` or `"remove"` (not `"delete"`) prevents mismatch between LLM prompt and backend validation.

---

### Issues

#### Bug — `change-reviewer.md` missing trailing newline

The file `.claude/agents/change-reviewer.md` does not end with a newline character. POSIX-compliant tools and some git diff viewers will flag this. Easy fix: add a newline at end of file.

#### Reliability gap — reviewer agent has no fallback

The updated `change-reviewer.md` calls `claude -p` to run the sub-agent review, but the review itself was blocked by sandbox write permissions during this very run. The agent description has no fallback instruction for when the write is blocked. Consider adding: "If the write to `planning/REVIEW.md` is blocked, print the review to stdout."

#### UX misleading label — `change_percent` is tick-to-tick, not daily

In Section 6 and Section 13, `change_percent` is described as the field that the watchlist displays as "daily change %". However, Section 13 also clarifies it "reflects change from the previous tick, not a true market-open baseline." Displaying a per-tick delta as "daily change %" is misleading to users. Either:
- Rename the UI label to "Change" or "Tick Δ", or
- Compute a true daily change by recording the day-open price in the price cache.

This is a product decision, but the current discrepancy between the label and the reality should be resolved explicitly in the plan rather than buried in a footnote.

#### Ops — `docker-compose.yml` lacks `restart` policy

The `docker-compose.yml` snippet in Section 13 has no `restart:` directive. Without it, if the container crashes (e.g., an unhandled exception in the background GBM task), it stays down until the user manually restarts it. Recommend adding `restart: unless-stopped` to the `app` service.

#### Ambiguity — `change_percent` units unclear

The example SSE payload shows `"change_percent": 0.2815`. It is not clear whether this means 0.2815% or 28.15% (i.e., is this a fraction or already multiplied by 100?). Given that AAPL moved $0.54 from $191.80, the correct daily change is ~0.28%, so `0.2815` appears to be the percentage value (not a fraction). This should be stated explicitly in the schema description to prevent frontend engineers from multiplying by 100 again.

---

## Summary

The changes are a net positive — Section 13 in particular significantly improves multi-agent coordination quality. The main issues to address before implementation begins are the `change_percent` labeling ambiguity and the missing units clarification in the SSE schema, both of which could cause frontend bugs. The Docker `restart` policy and reviewer fallback are lower priority but worth fixing.
