# Acceptance Results

Validated on 2026-10-18 with Python 3.12 on Windows, MCP 1.30.0 and HTTPX 0.28.1.

## Checks

- **Shared calculation:** 41 unit/integration tests pass, including 56 model/age/environment combinations and 27 tier/strength/model combinations. Every generated duration, TSS and work estimate matches its expanded steps. Published numerical examples remain unchanged.
- **Calendar reliability:** simulated API tests cover read-only preview, repeat-import no-op, changed workout update, moved-session ID preservation, stale previews, namespace collisions, partial writes, response timeout after success, failed read-back, empty parsed steps, wrong account FTP, retained removed sessions and sanitized HTTP errors. No blind POST retries occur.
- **Feasibility:** tests cover rest days, ride/day/week caps, load jumps, missing history/recovery/thresholds, high fatigue, FTP mismatch, TSS/PI conflicts and polarized/pyramidal targets.
- **Private state:** profile/plan snapshots survive reload; revisions record reasons and differences. Actual feedback retains the original prescription even after later changes; explicit earlier revisions are supported. Sync warning reasons and results are saved privately.
- **Offline files:** exported showcase ZWO parses as XML, totals exactly 3,600 seconds and 459.6 kJ at FTP 200 W. ICS passes an independent `icalendar` 7.3.0 parse and contains the expected local all-day date. Tests also check Unicode, escaping, UTF-8 line lengths and stable UIDs after a date change.
- **Real MCP transport:** stdio initialization lists all 11 tools and completes synthetic profile, plan, feedback and reload calls without an API key.
- **Live account read:** the shipped MCP server successfully reads the configured account and a calendar range with five existing workouts; all have parsed steps and resolved power. Only aggregate outcomes are recorded here.
- **Skill/documentation:** skill metadata validator passes; public Markdown links, bilingual command blocks and staged content are checked before commit.

Run the regression suite and transport smoke test with:

```powershell
python -m unittest discover -s tests -v
python tests/stdio_smoke.py
```

The independent ICS parse used a validation-only library; it is not a runtime dependency. Live write failure scenarios use a simulated API. This acceptance run created, modified and deleted **zero account calendar events**. Device delivery and receiving-app imports were not tested. The agent still authors training plans; the validator does not guarantee an optimal or physiologically safe prescription.
