import type { Register } from 'claude-code'

import { POLL_DENY, counts, isPollLoop, nudge, resets } from './drift'

export const register: Register = on => {
  let inline = 0

  on('tool.call', async ($, e, next) => {
    if (e.agentId) return next(e)

    if (resets(e.tool)) {
      inline = 0

      return next(e)
    }

    if (e.tool === 'Bash' && !e.run_in_background && isPollLoop(e.command)) {
      return { deny: POLL_DENY }
    }

    const ran = await next(e)

    if (!counts(e.tool) || ran.deny !== undefined) return ran

    inline += 1
    const note = nudge(inline)

    if (!note) return ran

    $.ui.toast(`${inline} inline calls since the last subagent`)

    return { ...ran, context: [...(ran.context ?? []), note] }
  })
}
