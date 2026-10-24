// A PreToolUse gate that denies reaches the mod layer as an errored result whose text begins with
// this prefix. An ordinary command failure never does.
export const wasDenied = (text: string | undefined): boolean => /^PreToolUse:[A-Za-z_]+ hook error/.test(text ?? '')

export const ROLLBACK =
  'rollback-notice: a gate denied this Bash call BEFORE it ran, so NOTHING in it executed: no earlier line, no heredoc, no file it was meant to write. Fix what the gate named, then re-run the ENTIRE command, never only the half that mattered. Any file this call was meant to create does not exist; a same-named file you find is someone else\'s.'

// git commit -F from the shared /tmp: a concurrent session's stale file became a commit message
//. The session scratchpad (/private/tmp/claude-<uid>/...) is exempt.
export const isSharedTmpCommit = (command: string): boolean =>
  /\bgit\b[^|;&\n]*\bcommit\b[^|;&\n]*\s(-F|--file(=|\s+))\s*(\/private)?\/tmp\/(?!claude-\d+\/)/.test(command)

export const SHARED_TMP_DENY =
  'rollback-notice: git commit -F reads from the shared /tmp, where a concurrent session may have left a stale file that would become the commit message. Write the message under the session scratchpad, or pipe it with -F - from a quoted heredoc, then check `git log -1 --format=%s` after.'
