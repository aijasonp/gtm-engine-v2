import type { Register } from 'claude-code'

import { ROLLBACK, SHARED_TMP_DENY, isSharedTmpCommit, wasDenied } from './guard'

export const register: Register = on => {
  on('tool.call', { tool: 'Bash' }, async (_$, e, next) => {
    if (isSharedTmpCommit(e.command)) return { deny: SHARED_TMP_DENY }

    const ran = await next(e)

    if (ran.isError !== true || !wasDenied(ran.text)) return ran

    return { ...ran, context: [...(ran.context ?? []), ROLLBACK] }
  })
}
