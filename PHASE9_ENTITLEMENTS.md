# Phase 9 — existing entitlement, not a new subscription

Actual account: **unverified**. No credential was available in the authorized environment, local app key file or Streamlit secrets file. No account request was made. GitHub secrets cannot be read back through this connector. The previous All-Star statement does not establish current access. No API credential belongs in this repository or a chat message.

The existing `phase8_access.py` is extended, not replaced. It now reports a sanitized NBA-only subscription state, current period end, scheduled cancellation, unknown renewal details and documented quota. An expired or malformed period cannot authorize free data reads. Missing period information remains explicitly unverified. Paid reads are disabled even when an active paid tier is reported. Unknown response strings/objects are not echoed. No `/me` call is needed.

The [Account API](https://www.balldontlie.io/account/) uses Bearer authentication; NBA data uses the raw key header. Two GETs suffice: plans/nba and subscriptions. Renewal fields are observations, not a promise of renewal, remaining credits or disabled overages. Published Free/All-Star/GOAT rates are 5/60/600 requests per minute. Current account limits still require inspection.

**The lineup endpoint is post-start only, from season 2025.** It cannot establish pre-tip starter confirmation. Plays also begin in season 2025. See the [official NBA documentation](https://docs.balldontlie.io/) and the complete [coverage matrix](validation/PHASE9_ENTITLEMENTS.json). No paid endpoint was probed, including for an expected authorization error.

## Trusted Windows computer: one command

From the development checkout containing this version, run:

```bat
.venv\Scripts\python.exe phase8_access.py inspect --state data/phase8/access.sqlite3 --enable-read-only --prompt-key
```

If `BALLDONTLIE_API_KEY` is already configured, it is reused. Otherwise the key is entered into a hidden local prompt, not a command argument. Do not enter it here. The command makes at most two read-only account requests, with one 13-second wait. It does not retry, change billing, enable polling or generate a prediction. Keep one state file across attempts. The global `APEX_AUTOMATION_DISABLED=true` switch blocks access. Keep output local: even a sanitized renewal date is account information. Do not upload it to public GitHub.

A missing/expired/ambiguous subscription or 401/403/429 stops the workflow. Check configuration and cooldown locally. No upgrade, trial activation or payment link is an automatic recovery step. Existing request budgets, official-host/path restrictions, bounded response size, persisted cooldowns and credential redaction remain intact. Local quotas do not coordinate multiple cloud machines; this client remains unwired from the cloud collector.

## Scope and shortest next step

Run this inspection locally before deciding whether existing access supplies anything beyond Free. All-Star's aggregates and injuries cannot replace opening events. If an already-active higher entitlement is discovered, review its limits and coverage before any additional endpoint use; this diagnostic deliberately does not unlock it. No new subscription is authorized.

The app version is 3.0.8; the registered model remains 3.0.6. This diagnostic release does not modify the frozen model or experiment. Level A remains blocked until a real authorized inspection succeeds.
