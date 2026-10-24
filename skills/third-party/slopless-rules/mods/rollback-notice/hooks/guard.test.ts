import { expect, test } from 'claude-code/testing'

import { isSharedTmpCommit, wasDenied } from './guard'

test('wasDenied: gate denials only', () => {
  expect(wasDenied('PreToolUse:Bash hook error: rm -rf is not allowed.')).toBe(true)
  expect(wasDenied('PreToolUse:Write hook error: canon not loaded')).toBe(true)
  expect(wasDenied('ls: /nonexistent: No such file or directory')).toBe(false)
  expect(wasDenied('Exit code 1\nPreToolUse:Bash hook error mentioned in output')).toBe(false)
  expect(wasDenied(undefined)).toBe(false)
})

test('isSharedTmpCommit: deny and allow cases', () => {
  expect(isSharedTmpCommit('git commit -F /tmp/msg.txt')).toBe(true)
  expect(isSharedTmpCommit('git -C repo commit -a --file=/private/tmp/msg.txt')).toBe(true)
  expect(isSharedTmpCommit('git commit -F /private/tmp/claude-501/x/scratchpad/msg.txt')).toBe(false)
  expect(isSharedTmpCommit('git commit -F -')).toBe(false)
  expect(isSharedTmpCommit('git commit -m "fix /tmp/msg.txt handling"')).toBe(false)
  expect(isSharedTmpCommit('git log -F /tmp/x')).toBe(false)
})
