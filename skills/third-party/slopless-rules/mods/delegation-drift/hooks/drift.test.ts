import { expect, test } from 'claude-code/testing'

import { counts, isPollLoop, nudge, resets } from './drift'

test('poll loops: deny and allow cases', () => {
  expect(isPollLoop('until ps -p 123 >/dev/null; do sleep 30; done')).toBe(true)
  expect(isPollLoop('while [ ! -f /tmp/done ]; do sleep 10; done')).toBe(true)
  expect(isPollLoop('sleep 3 && curl -s localhost:9')).toBe(false)
  expect(isPollLoop('for i in 1 2 3; do echo $i; done')).toBe(false)
  expect(isPollLoop('git log --since="until yesterday" | head')).toBe(false)
  expect(isPollLoop('while read -r l; do echo "$l"; done < f.txt')).toBe(false)
})

test('nudge fires on every tenth call only', () => {
  expect(nudge(9)).toBeUndefined()
  expect(nudge(10)).toBeDefined()
  expect(nudge(11)).toBeUndefined()
  expect(nudge(20)).toBeDefined()
  expect(nudge(0)).toBeUndefined()
})

test('which tools reset or count', () => {
  expect(resets('Agent')).toBe(true)
  expect(resets('Bash')).toBe(false)
  expect(counts('Bash')).toBe(true)
  expect(counts('Read')).toBe(false)
})
