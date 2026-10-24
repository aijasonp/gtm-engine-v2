# Contributing to no-slop

Thanks for helping make AI writing less detectable. Here's how to contribute.

## Adding banned words or phrases

1. Open `banned-vocabulary.md`
2. Add the word/phrase to the appropriate table
3. Include a plain alternative in the "Use instead" column
4. In your PR description, link to evidence — either the [Wikipedia article](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) or published research showing the word is overrepresented in AI text

Don't add words that are perfectly normal in human writing. The bar is: would a Wikipedia editor flag this as an AI tell?

## Adding examples

1. Add a "bad" example to `examples/bad-examples.md` with annotations for every AI pattern present
2. Add a matching "good" rewrite to `examples/good-examples.md` with a "Why this works" section
3. Examples should come from realistic contexts: project descriptions, emails, docs, blog posts, PR descriptions

## Adding rules

New rules should be backed by the Wikipedia article or equivalent evidence. Open an issue first to discuss before submitting a PR — this keeps the rule set focused.

## Adding agent support

If you use an AI tool that isn't covered in `agents/`, add a new file with install and usage instructions. Follow the format of the existing files.

## PR guidelines

- One rule, one example set, or one agent per PR
- Keep changes focused
- Test that your additions don't break existing SKILL.md formatting
- No promotional language in your PR description (practice what we preach)

## Code of conduct

Be direct, be helpful, don't waste people's time. That's it.
