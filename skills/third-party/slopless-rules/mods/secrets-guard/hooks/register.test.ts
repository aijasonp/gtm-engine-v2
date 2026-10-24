import { expect, test } from 'claude-code/testing'

import { checkBash, findCredential, isProtectedPath } from './register'

const fake = {
  anthropic: 'sk-' + 'ant-' + 'a'.repeat(30),
  pem: '-----BEGIN ' + 'PRIVATE KEY-----',
  url: 'postgresql://app:' + 'x'.repeat(14) + '@db:5432/x',
}

test('protected paths: deny cases', () => {
  for (const p of ['/a/.env', '/a/.env.local', '/h/.ssh/config', '/h/.aws/credentials', '/h/k/server.pem', '/h/.password-store/a.gpg'])
    expect(isProtectedPath(p)).toBe(true)
})

test('protected paths: allow cases', () => {
  for (const p of ['/a/.env.example', '/a/environment.ts', '/a/src/keys.ts', '/h/.ssh/id_rsa.pub', '/a/README.md', '/a/.envrc'])
    expect(isProtectedPath(p)).toBe(false)
})

test('credential content: deny and allow', () => {
  expect(findCredential(`k=${fake.anthropic}`)).toBeDefined()
  expect(findCredential(fake.pem)).toBeDefined()
  expect(findCredential(fake.url)).toBeDefined()
  expect(findCredential('api_key = os.environ["KEY"]')).toBeUndefined()
  expect(findCredential("grep -nE '://[A-Za-z0-9_.-]+:[A-Za-z0-9%._~-]{12,}@'")).toBeUndefined()
  expect(findCredential('postgresql://user@localhost/db')).toBeUndefined()
})

test('bash: writes and reads', () => {
  expect(checkBash('echo X > ~/.ssh/config')).toBeDefined()
  expect(checkBash('cp a /h/.aws/credentials')).toBeDefined()
  expect(checkBash('cat ~/.aws/credentials')).toBeDefined()
  expect(checkBash('cat .env')).toBeDefined()
  expect(checkBash('ls ~/.ssh')).toBeUndefined()
  expect(checkBash('cat .env.example')).toBeUndefined()
  expect(checkBash('git status && echo ok > /tmp/out.txt')).toBeUndefined()
  expect(checkBash('security find-generic-password -s api -w')).toBeUndefined()
  // real traffic that the first version blocked: a jq path and a stderr redirect
  expect(checkBash("jq -c '{a: .env.FLAG}' ~/.claude/settings.json 2>/dev/null")).toBeUndefined()
  expect(checkBash('ls ~/.claude/settings.local.json 2>&1; jq keys x.json 2>/dev/null')).toBeUndefined()
  expect(checkBash('echo hi >/dev/null 2>&1')).toBeUndefined()
  expect(checkBash('sed -i "" s/a/b/ /h/.aws/credentials')).toBeDefined()
  expect(checkBash('tee /h/.ssh/authorized_keys < in')).toBeDefined()
  expect(checkBash('echo x >> .env')).toBeDefined()
  expect(checkBash('cat a.txt | tee /tmp/o.txt')).toBeUndefined()
})
