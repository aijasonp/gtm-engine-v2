# Quality Gates

## Check the artifact, in this order: files, then logs, then docs

Never trust an exit code, a config, a green heartbeat, a freshness stamp, or your own prior
summary. Read the file, run a real request, look at the row. Logs come second (lagged,
level-filtered). Docs come last, and a memory or commit message that says "fixed" is a doc.

- An exit code lies in both directions. Gate on the file, row or URL produced, never on `$?`.
- HTTP 200 with an `errors[]` body is a failure.
- Never take "the last line of stdout" as a structured value. Match the thing you want, or fail.
- A send is proven by the artifact on the platform. Read it back.
- A freshness stamp that postdates its own file's mtime is self-refuting. Compare it to `stat`.
- Two timestamps are not comparable until they share a zone. `git log` prints local time, a
  database `timestamptz` often reads back UTC. Use `--date=iso-strict` and read the offset.
- An absence reported by a tool pointed at one path is a claim about that path. Name the paths
  you checked before writing "does not exist".
- A tool's defaults truncate silently. Check a list against its own summary count; a `--top`
  that defaults to 50 under a summary of 222 under-reports with no error.
- If numbers differ across sources, flag the discrepancy instead of picking one.
- Before documenting something as "running", check it is running. If not, write "planned".

## Never invent data to fill a gap

**No synthetic, mock, placeholder or example data unless it was asked for.** When the real
thing is unavailable, say it is unavailable. A fabricated value is indistinguishable from a
measured one downstream, and it propagates silently and confidently. Real examples: a digest
that emailed `INBOX SIZE: 0` for two weeks because the collector was dead and `|| echo 0`
supplied the zero (the real count was 31); a cost report headlined $7.11 against a real invoice
of $0.29, because a correction that could not read its input let the raw meter stand.

- Fixtures are fine and often required. Use documentation-safe values (RFC 5737
  `10.0.0.1/24`, `example.com`) so a fixture can never pass for real infrastructure.
- A default is not data. `return []` on an error path fabricates an empty result set. A
  missing-key read does it too: `d.get('ok')` against a log that records `status` reported
  "0 ok, 371 errors" against a real 321/50. Raise instead.
- A correction that cannot obtain its input must raise, not fall back to the value it corrects.
- An illustrative number in prose must be labelled as one.

The test: could a reader tell this value was not measured? If not, measure it or do not emit it.

## A gate you write is controlled in both directions, on real traffic

Running only the cases it should catch proves recall and says nothing about what it wrongly
catches. An over-firing gate gets muted, which ends the same as no gate.

- Draw the should-pass cases from the real corpus, not fixtures. Run a new gate over live data
  before wiring it in, and treat a high hit count as a precision problem first.
- A control that cannot run must fail, never print nothing. Put it in the tool as `--selftest`.
- A zero from a search or a needle you never positive-controlled is not a clean result.
- Where output is read rendered (email, PDF, page), assert on the rendered artifact, not the source.
- When the gate is wrong about a hit, add a suppressor. Editing the corpus to satisfy your own
  gate is the gate failing.
- A second check that reads the same text as the first is not a second opinion. Fan out only when
  each arm sees something the others cannot: execution results, rendered output, an external tool.

**Pass@k is a capability ceiling; pass^k predicts an unattended pipeline.** At p=0.6 and k=5,
pass@5 is about 99% and pass^5 is about 7.8%. Say which one you measured.

## Incremental over full

Indexing, syncs and builds run incremental by default. Full or clean only on request or corruption.
