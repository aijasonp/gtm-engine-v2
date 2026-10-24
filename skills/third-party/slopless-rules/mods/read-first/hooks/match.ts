export const isNotRead = (text: string | undefined): boolean => /has not been read yet/i.test(text ?? '')

export const headOf = (text: string | undefined, max = 6000): string => {
  const t = text ?? ''

  return t.length > max ? `${t.slice(0, max)}\n[... cut at ${max} characters]` : t
}
