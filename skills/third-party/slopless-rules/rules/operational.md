# Operational Rules

## Before a dev server

Check the port is free (`lsof -i:PORT`); if taken, use the next in range (Next.js 3000-3999,
Vite 5173-5179, FastAPI 8000-8099).

## API errors

- **403 is not 401.** A 403 from a third-party API usually means billing or entitlement, and
  re-authing does nothing. Probe a cheap authed read (`GET /v1/models`): 200 means the token is
  fine and it is a payment or plan problem.
- A set-but-invalid credential is worse than an absent one, because fallbacks gate on presence.
- For an unfamiliar external failure, search the exact error early. Never retry more than twice
  without a diagnosis, and never retry the identical command hoping for a different result.

## Is it alive?

- **A long job's liveness is a file it writes.** Have it append to a progress file; unchanged
  mtime for N minutes means stuck. A live process proves it exists, not that it is working.
- `pgrep -f` can match its own calling script, so a count proves nothing. Never gate a kill on a
  count. Print the rows and look.
- Killing a wrapper does not kill its children; they reparent to PID 1 and keep writing. Confirm
  by the artifact (did new output stop?), not by `ps -p` on the pids you killed.
- `kill -9 -$PGID` on an orphan can resolve the group to `1`, and `kill -9 -1` kills everything you
  own. Prefer explicit pids.
- An instrument pointed at something it cannot reach returns a plausible value. `systemctl show`
  prints compiled-in defaults for a unit it cannot find; an empty `FragmentPath=` is the tell.
- `systemctl start` on an active oneshot unit is a no-op. Use `restart`, and check `--user` vs system.

## Shell traps that exit 0

- **`$?` after a pipeline is the last stage's.** With `pipefail`, an early-exit consumer
  (`grep -q`, `head`) returns 141 on a successful match. Piping a captured variable has the same
  bug, only once it exceeds the pipe buffer. Remove the pipe: `[[ "$out" == *"$needle"* ]]`.
- **A zero-result search is a claim about your instrument.** `grep -r` and `find` skip symlinked
  dirs (use `-R`, `-L`); a `grep` aliased to a gitignore-aware tool skips ignored files. Never `2>/dev/null` a search you
  will draw a conclusion from, and positive-control every zero.
- `rsync -an` prints nothing no matter what it would delete. Use `rsync -ain --delete`. Never pass
  a delete flag (`--delete-excluded` implies one) on an overlay copy.
- An unquoted `<<EOF` heredoc expands `$VAR`, `$(...)` and backticks, so a commit message loses
  every backticked span. Quote the delimiter: `<<'EOF'`.
- A hook denial rolls back the whole Bash call. Re-run all of it, not just the half that mattered.
- `ssh host 'cmd'` with no stdin redirect drains the caller's stdin; add `</dev/null`.
- `open(f,"w").write(x + open(f).read())` truncates the file before the read.
