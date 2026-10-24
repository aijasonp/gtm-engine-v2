#!/usr/bin/env node
// Notion page → Markdown converter
// Usage: node notion-to-md.mjs <page-id> [--output <file>]

import { createRequire } from "module";
const require = createRequire(import.meta.url);

const { Client } = require("@notionhq/client");
const { NotionToMarkdown } = require("notion-to-md");
const fs = require("fs");
const path = require("path");

const args = process.argv.slice(2);
if (args.length === 0 || args[0] === "--help") {
  console.error("Usage: node notion-to-md.mjs <page-id> [--output <file>]");
  process.exit(1);
}

const pageId = args[0];
let outputFile = null;
const outputIdx = args.indexOf("--output");
if (outputIdx !== -1 && args[outputIdx + 1]) {
  outputFile = args[outputIdx + 1];
}

const apiKey = fs.readFileSync(
  path.join(process.env.HOME, ".config/notion/api_key"),
  "utf-8"
).trim();

const notion = new Client({ auth: apiKey });
const n2m = new NotionToMarkdown({ notionClient: notion });

try {
  const blocks = await n2m.pageToMarkdown(pageId);
  const md = n2m.toMarkdownString(blocks);
  // notion-to-md v3+ returns { parent: string }, v2 returns string
  const content = typeof md === "string" ? md : md.parent;

  if (outputFile) {
    fs.writeFileSync(outputFile, content);
    console.error(`Written to ${outputFile}`);
  } else {
    process.stdout.write(content);
  }
} catch (err) {
  console.error(`Error: ${err.message}`);
  process.exit(1);
}
