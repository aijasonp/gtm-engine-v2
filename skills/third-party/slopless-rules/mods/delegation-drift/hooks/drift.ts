export const STEP = 10

const DISPATCHERS = new Set(['Agent', 'Workflow', 'Monitor'])
const ACTION_TOOLS = new Set(['Bash', 'Edit', 'Write', 'NotebookEdit'])

export const resets = (tool: string): boolean => DISPATCHERS.has(tool)
export const counts = (tool: string): boolean => ACTION_TOOLS.has(tool)

// until/while around a sleep of five seconds or more, the shape that holds the session.
export const isPollLoop = (command: string): boolean =>
  /\b(until|while)\b[\s\S]*\bsleep\s+([5-9]|\d{2,})\b/.test(command)

export const nudge = (count: number): string | undefined =>
  count > 0 && count % STEP === 0
    ? `delegation-drift: ${count} main-thread Bash/Edit/Write calls since the last subagent dispatch. A job of five or more shell or remote calls with a known sequence, or an edit across three or more files, is a delegable job (rules/subagent-models.md). Dispatch it, run it in the background, or say why this one is iterative.`
    : undefined

export const POLL_DENY =
  'delegation-drift: a foreground poll loop holds the session while it waits. Re-issue with run_in_background: true (you are notified when it exits) or use Monitor; do not poll for a subagent, the harness re-invokes you when it finishes.'
