# Pre-Call Brief Template — PERMANENT (Jason Polanco, 2026-09-23)

**Every pre-call brief must be 2 PAGES MAX in the Google Doc.** Jason's rule: "no longer than 2 pages." Cut ruthlessly — every line must earn its place. If a section doesn't change what the rep says or asks on the call, delete it.

## Format
- {{COMPANY}} approved doc format (`references/company-doc-format.md`): white bg, Inter, 22pt orange title, 14pt Ink H2, 10pt Ink body, gray dividers, arrow lists (`→  `), zero Google bullets.
- Build pattern: `output/build-precall-gdoc.py` (create → insert → read back boundaries → style by kind → deleteParagraphBullets sweep → white bg → share per request).
- Share scope: exactly who the requester names, nobody else.

## Structure (this order, ~40 content lines total)
1. **Header block** — company® brand line, title `PRE-CALL BRIEF: <COMPANY> — <TOPIC>`, subtitle: generated date · meeting date/time in UTC + local zones · read time · confidentiality.
2. **COMPANY SNAPSHOT** — 3-4 lines max: industry, size, HQ, ownership (only if strategically relevant), ICP fit, HubSpot status.
3. **MEETING CONTEXT** — 2-3 lines: origin (how we met), booking/reschedule history if it signals something, {{COMPANY}} attendees, goal.
4. **ATTENDEES** — 1 line per person, name + title + why they matter. Partners called out in one line.
5. **PAIN POINTS TO ANCHOR ON** — 3 lines max, only the sharpest ones.
6. **DEMO FOCUS** — 3 lines max: what to lead with, what compliance language to use, what NOT to wander into.
7. **KEY QUESTIONS TO ASK** — 4 max.
8. **LIKELY OBJECTIONS** — 3 max, each with a one-line counter.
9. **RECOMMENDED PLAY** — 3-4 sentences, one paragraph. The actual call strategy.
10. **KEY FACTS TO HAVE READY** — 3 lines max, only facts that answer questions likely to come up.

## Sourcing checklist (before writing)
- HubSpot contact + company record (properties, owner, lifecycle, last touched)
- HubSpot engagements (recent emails/notes/meetings — read actual bodies for tone + commitments)
- Calendar event (attendees, acceptance status, description) via `gwsg calendar events list --params '{"calendarId":...}'`
- Account-knowledge store (`account-knowledge/<company>.md`) if it exists
- Requester-supplied links (fetch them)
- Prior briefs for the same account — update, don't duplicate

## Voice
- No em dashes, no AI slop, direct and specific. Write like a sharp SE's prep notes, not a research report.
- Customer name isolation: never name a second customer anywhere in the brief.
