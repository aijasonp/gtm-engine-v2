import type { Register } from 'claude-code'

// Placeholder files carry no secrets and are meant to be edited and committed.
const EXEMPT = /\.(example|template|sample|pub)$/i

const PROTECTED_PATHS: RegExp[] = [
  /(^|\/)\.env(\.[^/]+)?$/,
  /\.(pem|key|p12|pfx)$/i,
  /(^|\/)id_(rsa|dsa|ecdsa|ed25519)$/,
  /(^|\/)\.ssh\//,
  /(^|\/)\.aws\/(credentials|config)$/,
  /(^|\/)\.password-store\//,
  /(^|\/)\.gnupg\//,
  /(^|\/)\.(netrc|npmrc|pypirc)$/,
]

// Credential shapes. Built from fragments so this file never contains a literal match.
const CONTENT: Array<[string, RegExp]> = [
  ['private key block', new RegExp('-----BEGIN ' + '(RSA |EC |DSA |OPENSSH |)PRIVATE KEY-----')],
  ['Anthropic API key', new RegExp('sk-' + 'ant-[A-Za-z0-9_-]{20,}')],
  ['AWS access key id', new RegExp('AK' + 'IA[0-9A-Z]{16}')],
  ['GitHub token', new RegExp('gh[pousr]' + '_[A-Za-z0-9]{36,}')],
  ['Slack token', new RegExp('xox' + '[bpac]-[A-Za-z0-9-]{20,}')],
  ['credential inside a URL', /:\/\/[A-Za-z0-9_.-]+:[A-Za-z0-9%._~-]{12,}@/],
]

const READ_VERBS = new Set(['cat', 'less', 'more', 'head', 'tail', 'bat', 'nl', 'strings', 'xxd', 'base64'])
const WRITE_VERBS = new Set(['cp', 'mv', 'install', 'tee'])
const READ_DENIED: RegExp[] = [
  /(^|\/)\.env(\.[^/]+)?$/,
  /(^|\/)id_(rsa|dsa|ecdsa|ed25519)$/,
  /\.aws\/credentials$/,
]

const clean = (w: string): string => w.replace(/^["'(]+|["'),;]+$/g, '')

export const isProtectedPath = (p: string): boolean =>
  !EXEMPT.test(p) && PROTECTED_PATHS.some(re => re.test(p))

export const findCredential = (text: string): string | undefined =>
  CONTENT.find(([, re]) => re.test(text))?.[0]

// Only real write targets and reader arguments count. A jq path such as `.env.X`, or a `2>/dev/null`
// elsewhere in the command, is not a write to a secret file.
export const checkBash = (command: string): string | undefined => {
  const targets: string[] = []

  for (const m of command.matchAll(/(?:^|[^0-9&>])>>?\s*(["']?)([^\s;&|"']+)/g)) if (m[2]) targets.push(m[2])

  for (const segment of command.split(/[;&|\n]+/)) {
    const words = segment.trim().split(/\s+/).map(clean).filter(Boolean)
    const verb = words[0]?.split('/').pop() ?? ''
    const isSed = verb === 'sed' && words.some(w => /^-[a-z]*i/.test(w))
    const isDd = verb === 'dd' && words.some(w => w.startsWith('of='))

    if (WRITE_VERBS.has(verb) || isSed) targets.push(...words.slice(1))
    if (isDd) targets.push(...words.filter(w => w.startsWith('of=')).map(w => w.slice(3)))

    if (READ_VERBS.has(verb)) {
      const secret = words.slice(1).find(w => !EXEMPT.test(w) && READ_DENIED.some(re => re.test(w)))

      if (secret) return `Bash would print ${secret}, a secret file. Read the one value through your secret manager instead.`
    }
  }

  const touched = targets.map(clean).find(isProtectedPath)

  return touched ? `Bash would write to ${touched}, a secret location. Use a secret manager.` : undefined
}

export const checkWrite = (path: string, text: string): string | undefined => {
  if (isProtectedPath(path)) return `${path} is a secret location. Store the value in a secret manager, not a file.`
  const found = findCredential(text)

  return found ? `the text to write contains a ${found}. Put it in a secret manager.` : undefined
}

export const register: Register = on => {
  const refuse = (name: string, why: string) => ({ deny: `${name}: ${why}` })

  on('tool.call', { tool: 'Edit' }, ($, e, next) => {
    const why = checkWrite(e.file_path, e.new_string)

    return why ? refuse($.plugin.name, why) : next(e)
  })

  on('tool.call', { tool: 'Write' }, ($, e, next) => {
    const why = checkWrite(e.file_path, e.content)

    return why ? refuse($.plugin.name, why) : next(e)
  })

  on('tool.call', { tool: 'NotebookEdit' }, ($, e, next) => {
    const found = findCredential(e.new_source)

    return found ? refuse($.plugin.name, `the cell contains a ${found}. Put it in a secret manager.`) : next(e)
  })

  on('tool.call', { tool: 'Bash' }, ($, e, next) => {
    const why = checkBash(e.command)

    return why ? refuse($.plugin.name, why) : next(e)
  })
}
