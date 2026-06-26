import fs from "node:fs/promises";

const seedPath = process.argv[2];

if (!seedPath) {
  console.error(
    "Usage: node scripts/import_curated_notes.mjs ./technical-notes-seed.json",
  );
  process.exit(1);
}

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8000/api/v1";
const ADMIN_TOKEN = process.env.ADMIN_TOKEN;

if (!ADMIN_TOKEN) {
  console.error("Missing ADMIN_TOKEN environment variable.");
  process.exit(1);
}

function chunk(items, size) {
  const chunks = [];

  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }

  return chunks;
}

function normalizeTopic(topic, index) {
  return {
    id: topic.id,
    slug: topic.id,
    title: topic.title,
    summary: topic.summary || null,
    group: topic.group || topic.domain || "Reference",
    domain: topic.domain || topic.group || "Reference",
    content: topic.content || "",
    sections: Array.isArray(topic.sections) ? topic.sections : [],
    sourceFiles: Array.isArray(topic.sourceFiles) ? topic.sourceFiles : [],
    order_index: Number.isInteger(topic.order_index)
      ? topic.order_index
      : index,
    status: "published",
    content_format: "markdown",
    is_featured: false,
    metadata: {
      ...(topic.metadata || {}),
      migratedFrom: "frontend-curatedNotes",
      originalFrontendId: topic.id,
    },
    extra: {
      frontend: {
        searchTextLength: topic.metadata?.frontendSearchTextLength || 0,
      },
    },
  };
}

async function postBulk(topics, batchIndex, totalBatches) {
  const response = await fetch(`${API_BASE_URL}/admin/topics/bulk-upsert-fast?rebuild_bootstrap=false`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": ADMIN_TOKEN,
    },
    body: JSON.stringify({
      mode: "upsert",
      topics,
    }),
    signal: AbortSignal.timeout(10 * 60 * 1000),
  });

  const text = await response.text();

  if (!response.ok) {
    console.error(`Batch ${batchIndex + 1}/${totalBatches} failed`);
    console.error(text);
    process.exit(1);
  }

  const data = JSON.parse(text);
  console.log(
    `Imported batch ${batchIndex + 1}/${totalBatches}: ${data.count ?? data.length ?? 0} topics`,
  );
}

const raw = await fs.readFile(seedPath, "utf-8");
const seed = JSON.parse(raw);

const sourceTopics = Array.isArray(seed) ? seed : seed.topics;

if (!Array.isArray(sourceTopics) || sourceTopics.length === 0) {
  console.error("No topics found in seed file.");
  process.exit(1);
}

const topics = sourceTopics.map(normalizeTopic);

console.log(`Found ${topics.length} topics to import.`);
console.log(`API: ${API_BASE_URL}`);

const batches = chunk(topics, Number(process.env.BATCH_SIZE || 25));

for (let index = 0; index < batches.length; index += 1) {
  await postBulk(batches[index], index, batches.length);
}

console.log("Import complete.");


async function rebuildBootstrap() {
  const response = await fetch(`${API_BASE_URL}/admin/cache/bootstrap/rebuild`, {
    method: "POST",
    headers: { "X-Admin-Token": ADMIN_TOKEN },
    signal: AbortSignal.timeout(10 * 60 * 1000),
  });
  const text = await response.text();
  if (!response.ok) {
    console.warn("Bootstrap rebuild failed:", text);
    return;
  }
  console.log("Bootstrap cache rebuilt:", text);
}

await rebuildBootstrap();
