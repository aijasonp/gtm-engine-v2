#!/usr/bin/env node
// Convert markdown file to Notion block JSON
import { markdownToBlocks } from '@tryfabric/martian';
import { readFileSync } from 'fs';

const filePath = process.argv[2];
if (!filePath) {
  console.error('Usage: node md-to-notion.mjs <markdown-file>');
  process.exit(1);
}

const md = readFileSync(filePath, 'utf-8');
const blocks = markdownToBlocks(md);
console.log(JSON.stringify(blocks, null, 2));
