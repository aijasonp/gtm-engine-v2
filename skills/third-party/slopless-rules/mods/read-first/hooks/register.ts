import type { Register } from 'claude-code'

import { headOf, isNotRead } from './match'

export const register: Register = on => {
  // Edit: the old_string must match the file exactly, so an engine-side read cannot let an
  // unseen edit clobber anything. Read it, then run the same call once more.
  on('tool.call', { tool: 'Edit' }, async ($, e, next) => {
    const ran = await next(e)

    if (e.agentId || ran.isError !== true || !isNotRead(ran.text)) return ran

    await $.tool.call({ tool: 'Read', file_path: e.file_path })

    return next(e)
  })

  // Write over an existing file would replace content the model never saw, so the model gets
  // the file's head with the error and decides.
  on('tool.call', { tool: 'Write' }, async ($, e, next) => {
    const ran = await next(e)

    if (e.agentId || ran.isError !== true || !isNotRead(ran.text)) return ran

    const read = await $.tool.call({ tool: 'Read', file_path: e.file_path })

    return {
      ...ran,
      context: [
        `read-first: ${e.file_path} exists and had not been read. It is read now. Head of the file:\n${headOf(read.text)}\nRe-issue the Write only if replacing this content is intended.`,
      ],
    }
  })
}
