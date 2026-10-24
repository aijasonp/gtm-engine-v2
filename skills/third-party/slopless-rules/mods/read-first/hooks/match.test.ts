import { expect, test } from 'claude-code/testing'

import { headOf, isNotRead } from './match'

test('isNotRead: engine wording only', () => {
  expect(isNotRead('Error: File has not been read yet. Read it first before writing to it.')).toBe(true)
  expect(isNotRead('String to replace not found in file.')).toBe(false)
  expect(isNotRead(undefined)).toBe(false)
})

test('headOf cuts long files and keeps short ones', () => {
  expect(headOf('abc', 10)).toBe('abc')
  expect(headOf('x'.repeat(50), 10)).toContain('cut at 10 characters')
  expect(headOf('x'.repeat(50), 10).startsWith('xxxxxxxxxx')).toBe(true)
})
