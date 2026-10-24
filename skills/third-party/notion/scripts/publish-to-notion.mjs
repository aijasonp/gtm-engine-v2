#!/usr/bin/env node
// Create a Notion page from markdown, handling 100-block batching
import { markdownToBlocks } from '@tryfabric/martian';
import { readFileSync } from 'fs';

const NOTION_KEY = readFileSync(process.env.HOME + '/.config/notion/api_key', 'utf-8').trim();
const PARENT_PAGE_ID = process.argv[2];
const TITLE = process.argv[3];
const MD_FILE = process.argv[4];

if (!PARENT_PAGE_ID || !TITLE || !MD_FILE) {
  console.error('Usage: node publish-to-notion.mjs <parent-page-id> "Title" <markdown-file>');
  process.exit(1);
}

const md = readFileSync(MD_FILE, 'utf-8');
const allBlocks = markdownToBlocks(md);
console.log(`Total blocks: ${allBlocks.length}`);

const BATCH = 100;

async function notionFetch(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${NOTION_KEY}`,
      'Notion-Version': '2022-06-28',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Notion API ${res.status}: ${text}`);
  }
  return res.json();
}

// Create page with first batch
const firstBatch = allBlocks.slice(0, BATCH);
const createBody = {
  parent: { page_id: PARENT_PAGE_ID },
  properties: { title: [{ text: { content: TITLE } }] },
  children: firstBatch,
};

const page = await notionFetch('https://api.notion.com/v1/pages', createBody);
console.log(`Created page: ${page.id}`);
console.log(`URL: ${page.url}`);

// Append remaining batches
for (let i = BATCH; i < allBlocks.length; i += BATCH) {
  const batch = allBlocks.slice(i, i + BATCH);
  console.log(`Appending blocks ${i}-${i + batch.length}...`);
  await new Promise(r => setTimeout(r, 500)); // rate limit
  const pageId = page.id;
  const res2 = await fetch(`https://api.notion.com/v1/blocks/${pageId}/children`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${NOTION_KEY}`,
      'Notion-Version': '2022-06-28',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ children: batch }),
  });
  if (!res2.ok) {
    const text = await res2.text();
    throw new Error(`Notion API ${res2.status}: ${text}`);
  }
}

console.log('Done!');
