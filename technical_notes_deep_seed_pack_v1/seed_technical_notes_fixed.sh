#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-https://technical-notes-backend.onrender.com}"
SEED_FILE="${1:-technical_notes_deep_seed_chunk_v1_fixed_no_html_anchors.json}"



if [[ ! -f "$SEED_FILE" ]]; then
  echo "Seed file not found: $SEED_FILE" >&2
  exit 1
fi

echo "Seeding fixed notes from: $SEED_FILE"
curl -f -X POST "$API_BASE/api/v1/admin/topics/bulk-upsert-fast?rebuild_bootstrap=true" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: zvn3Iv1JoWSurN9IaoNbfo+Q7QDvHwOgzLn9WUFyl2Y=" \
  --data-binary "@$SEED_FILE"

echo
echo "Rebuilding topic-detail cache so old cached markdown does not keep showing..."
curl -f -X POST "$API_BASE/api/v1/admin/cache/topics/rebuild?include_sources=true&include_section_bodies=true&limit=5000" \
  -H "X-Admin-Token: zvn3Iv1JoWSurN9IaoNbfo+Q7QDvHwOgzLn9WUFyl2Y="

echo
echo "Rebuilding bootstrap cache..."
curl -f -X POST "$API_BASE/api/v1/admin/cache/bootstrap/rebuild" \
  -H "X-Admin-Token: zvn3Iv1JoWSurN9IaoNbfo+Q7QDvHwOgzLn9WUFyl2Y="

echo
echo "Done. Hard-refresh the frontend after this."
