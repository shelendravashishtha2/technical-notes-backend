#!/usr/bin/env python3

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GROUP_COLUMNS = [
    "id",
    "slug",
    "name",
    "description",
    "sort_order",
    "metadata_json",
    "created_at",
    "updated_at",
]

DOMAIN_COLUMNS = [
    "id",
    "slug",
    "name",
    "description",
    "sort_order",
    "metadata_json",
    "created_at",
    "updated_at",
]

TOPIC_COLUMNS = [
    "id",
    "slug",
    "title",
    "subtitle",
    "summary",
    "group_id",
    "domain_id",
    "parent_topic_id",
    "status",
    "content_format",
    "difficulty",
    "body_markdown",
    "body_plain_text",
    "body_hash",
    "reading_time_minutes",
    "word_count",
    "section_count",
    "order_index",
    "version",
    "is_featured",
    "published_at",
    "source_checksum",
    "metadata_json",
    "extra_json",
    "created_at",
    "updated_at",
    "deleted_at",
]

SECTION_COLUMNS = [
    "id",
    "topic_id",
    "parent_section_id",
    "slug",
    "anchor",
    "title",
    "level",
    "order_index",
    "materialized_path",
    "body_markdown",
    "body_plain_text",
    "body_hash",
    "word_count",
    "reading_time_minutes",
    "metadata_json",
    "created_at",
    "updated_at",
    "deleted_at",
]

SOURCE_FILE_COLUMNS = [
    "id",
    "source_key",
    "display_name",
    "path",
    "checksum",
    "mime_type",
    "size_bytes",
    "metadata_json",
    "created_at",
    "updated_at",
]

TOPIC_SOURCE_LINK_COLUMNS = [
    "topic_id",
    "source_id",
    "relevance",
]


COPY_COMMANDS = {
    "groups": (
        GROUP_COLUMNS,
        "groups",
    ),
    "domains": (
        DOMAIN_COLUMNS,
        "domains",
    ),
    "topics": (
        TOPIC_COLUMNS,
        "topics",
    ),
    "topic_sections": (
        SECTION_COLUMNS,
        "topic_sections",
    ),
    "source_files": (
        SOURCE_FILE_COLUMNS,
        "source_files",
    ),
    "topic_source_links": (
        TOPIC_SOURCE_LINK_COLUMNS,
        "topic_source_links",
    ),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def slugify(value: str, fallback: str = "item") -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or fallback


def strip_markdown(value: str) -> str:
    text = value or ""

    # Remove fenced code block markers but keep inner code text searchable.
    text = re.sub(r"```[a-zA-Z0-9_-]*", " ", text)
    text = text.replace("```", " ")

    # Remove markdown images/links but keep visible label.
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove common markdown syntax.
    text = re.sub(r"[#>*_`~|]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^A-Za-z0-9+/_.:-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def word_count(value: str) -> int:
    if not value:
        return 0
    return len(re.findall(r"\b\w+\b", value))


def reading_time_minutes(words: int) -> int:
    return max(1, round(words / 220)) if words else 1


def ensure_unique_slug(base_slug: str, used: set[str]) -> str:
    slug = base_slug
    counter = 2

    while slug in used:
        slug = f"{base_slug}-{counter}"
        counter += 1

    used.add(slug)
    return slug


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, separators=(",", ":"))


def guess_mime_type(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def run_psql(
    conn: str,
    sql: str,
    *,
    retries: int = 3,
    sleep_seconds: int = 4,
    label: str = "psql command",
) -> None:
    last_error: subprocess.CalledProcessError | None = None

    for attempt in range(1, retries + 1):
        print(f"→ {label} | attempt {attempt}/{retries}")

        result = subprocess.run(
            [
                "psql",
                conn,
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                sql,
            ],
            text=True,
            capture_output=True,
        )

        if result.returncode == 0:
            if result.stdout.strip():
                print(result.stdout.strip())
            return

        last_error = subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )

        print(result.stderr.strip() or result.stdout.strip())

        if attempt < retries:
            print(f"Retrying in {sleep_seconds}s...\n")
            time.sleep(sleep_seconds)

    raise last_error


def copy_csv(conn: str, table_name: str, columns: list[str], csv_path: Path, retries: int) -> None:
    # psql \copy is a psql meta-command, not normal SQL.
    # It must be passed as a single -c command.
    column_list = ",".join(columns)
    safe_path = str(csv_path.resolve()).replace("'", "''")

    sql = (
        f"\\copy {table_name}({column_list}) "
        f"FROM '{safe_path}' "
        f"WITH (FORMAT csv, HEADER true)"
    )

    run_psql(
        conn,
        sql,
        retries=retries,
        label=f"COPY {table_name} from {csv_path.name}",
    )


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            quoting=csv.QUOTE_MINIMAL,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:
            clean_row = {}

            for col in columns:
                value = row.get(col)

                if value is None:
                    clean_row[col] = ""
                elif isinstance(value, (dict, list)):
                    clean_row[col] = json_dumps(value)
                else:
                    clean_row[col] = value

            writer.writerow(clean_row)


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def write_batched_csvs(
    output_dir: Path,
    prefix: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    batch_size: int,
) -> list[Path]:
    files = []

    for index, batch in enumerate(chunked(rows, batch_size), start=1):
        path = output_dir / f"{prefix}_part_{index:04d}.csv"
        write_csv(path, columns, batch)
        files.append(path)

    return files


def build_rows(seed_path: Path) -> dict[str, list[dict[str, Any]]]:
    raw = json.loads(seed_path.read_text(encoding="utf-8"))

    if isinstance(raw, list):
        topics = raw
        group_order_preference = []
    else:
        topics = raw.get("topics", [])
        group_order_preference = raw.get("groupOrderPreference", [])

    if not isinstance(topics, list) or not topics:
        raise ValueError("No topics found. Expected JSON with a non-empty topics array.")

    created_at = now_iso()

    group_ids: dict[str, str] = {}
    domain_ids: dict[str, str] = {}
    source_ids: dict[str, str] = {}

    group_rows: list[dict[str, Any]] = []
    domain_rows: list[dict[str, Any]] = []
    topic_rows: list[dict[str, Any]] = []
    section_rows: list[dict[str, Any]] = []
    source_file_rows: list[dict[str, Any]] = []
    topic_source_link_rows: list[dict[str, Any]] = []

    group_order = {
        name: index
        for index, name in enumerate(group_order_preference)
    }

    seen_group_slugs: set[str] = set()
    seen_domain_slugs: set[str] = set()

    def get_group_id(name: str) -> str:
        clean_name = name or "Reference"
        slug = slugify(clean_name, "reference")

        if slug in group_ids:
            return group_ids[slug]

        group_id = str(uuid.uuid4())
        group_ids[slug] = group_id
        seen_group_slugs.add(slug)

        group_rows.append(
            {
                "id": group_id,
                "slug": slug,
                "name": clean_name,
                "description": None,
                "sort_order": group_order.get(clean_name, len(group_rows)),
                "metadata_json": {},
                "created_at": created_at,
                "updated_at": created_at,
            }
        )

        return group_id

    def get_domain_id(name: str) -> str:
        clean_name = name or "Reference"
        slug = slugify(clean_name, "reference")

        if slug in domain_ids:
            return domain_ids[slug]

        domain_id = str(uuid.uuid4())
        domain_ids[slug] = domain_id
        seen_domain_slugs.add(slug)

        domain_rows.append(
            {
                "id": domain_id,
                "slug": slug,
                "name": clean_name,
                "description": None,
                "sort_order": len(domain_rows),
                "metadata_json": {},
                "created_at": created_at,
                "updated_at": created_at,
            }
        )

        return domain_id

    def get_source_id(source_name: str) -> str:
        clean_source = str(source_name or "").strip()

        if not clean_source:
            clean_source = "unknown-source"

        checksum = sha256_text(clean_source)
        source_key = f"{slugify(clean_source, 'source')}-{checksum[:10]}"

        if source_key in source_ids:
            return source_ids[source_key]

        source_id = str(uuid.uuid4())
        source_ids[source_key] = source_id

        source_file_rows.append(
            {
                "id": source_id,
                "source_key": source_key,
                "display_name": clean_source,
                "path": clean_source,
                "checksum": checksum,
                "mime_type": guess_mime_type(clean_source),
                "size_bytes": None,
                "metadata_json": {},
                "created_at": created_at,
                "updated_at": created_at,
            }
        )

        return source_id

    seen_topic_slugs: set[str] = set()

    for topic_index, topic in enumerate(topics):
        frontend_id = str(topic.get("id") or f"topic-{topic_index + 1}")
        title = str(topic.get("title") or frontend_id)
        topic_slug = ensure_unique_slug(slugify(frontend_id or title, f"topic-{topic_index + 1}"), seen_topic_slugs)

        group_name = str(topic.get("group") or topic.get("domain") or "Reference")
        domain_name = str(topic.get("domain") or topic.get("group") or "Reference")

        group_id = get_group_id(group_name)
        domain_id = get_domain_id(domain_name)

        content = str(topic.get("content") or "")
        plain_text = strip_markdown(content)
        wc = word_count(plain_text)
        section_count = len(topic.get("sections") or [])

        topic_id = str(uuid.uuid4())
        source_files = topic.get("sourceFiles") or []

        topic_rows.append(
            {
                "id": topic_id,
                "slug": topic_slug,
                "title": title,
                "subtitle": None,
                "summary": topic.get("summary") or None,
                "group_id": group_id,
                "domain_id": domain_id,
                "parent_topic_id": None,
                "status": "published",
                "content_format": "markdown",
                "difficulty": None,
                "body_markdown": content,
                "body_plain_text": plain_text,
                "body_hash": sha256_text(content),
                "reading_time_minutes": reading_time_minutes(wc),
                "word_count": wc,
                "section_count": section_count,
                "order_index": topic_index,
                "version": 1,
                "is_featured": "false",
                "published_at": created_at,
                "source_checksum": sha256_text(json_dumps(source_files) + content),
                "metadata_json": {
                    "frontendId": frontend_id,
                    "migratedFrom": "frontend-curatedNotes",
                },
                "extra_json": {
                    "sourceFiles": source_files,
                },
                "created_at": created_at,
                "updated_at": created_at,
                "deleted_at": None,
            }
        )

        used_section_slugs: set[str] = set()

        for section_index, section in enumerate(topic.get("sections") or []):
            raw_section_id = str(section.get("id") or section.get("title") or f"section-{section_index + 1}")
            section_slug = ensure_unique_slug(slugify(raw_section_id, f"section-{section_index + 1}"), used_section_slugs)
            section_title = str(section.get("title") or section_slug)
            body_markdown = str(section.get("rawText") or "\n".join(section.get("raw") or []) or "")
            body_plain = str(section.get("plainText") or strip_markdown(body_markdown))
            section_wc = word_count(body_plain)

            section_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "topic_id": topic_id,
                    "parent_section_id": None,
                    "slug": section_slug,
                    "anchor": section_slug,
                    "title": section_title,
                    "level": int(section.get("level") or 2),
                    "order_index": section_index,
                    "materialized_path": section_slug,
                    "body_markdown": body_markdown,
                    "body_plain_text": body_plain,
                    "body_hash": sha256_text(body_markdown),
                    "word_count": section_wc,
                    "reading_time_minutes": reading_time_minutes(section_wc),
                    "metadata_json": {
                        "frontendSectionId": raw_section_id,
                    },
                    "created_at": created_at,
                    "updated_at": created_at,
                    "deleted_at": None,
                }
            )

        for source in source_files:
            source_id = get_source_id(str(source))

            topic_source_link_rows.append(
                {
                    "topic_id": topic_id,
                    "source_id": source_id,
                    "relevance": 1,
                }
            )

    return {
        "groups": group_rows,
        "domains": domain_rows,
        "topics": topic_rows,
        "topic_sections": section_rows,
        "source_files": source_file_rows,
        "topic_source_links": topic_source_link_rows,
    }


def clean_database(conn: str, retries: int) -> None:
    sql = """
TRUNCATE TABLE
  audit_logs,
  topic_source_links,
  source_files,
  topic_sections,
  topic_revisions,
  topic_collection_links,
  topic_assets,
  topics,
  domains,
  groups
RESTART IDENTITY CASCADE;
"""

    run_psql(conn, sql, retries=retries, label="Clean existing notes data")


def verify_counts(conn: str, retries: int) -> None:
    sql = """
select
  (select count(*) from groups) as groups,
  (select count(*) from domains) as domains,
  (select count(*) from topics) as topics,
  (select count(*) from topic_sections) as sections,
  (select count(*) from source_files) as source_files,
  (select count(*) from topic_source_links) as topic_source_links;
"""

    run_psql(conn, sql, retries=retries, label="Verify imported row counts")


def refresh_search(conn: str, retries: int) -> None:
    sql = "select refresh_topic_search_vectors();"
    run_psql(conn, sql, retries=retries, label="Refresh search vectors")


def check_psql_exists() -> None:
    if not shutil.which("psql"):
        raise RuntimeError(
            "psql was not found. Install it first. On macOS: brew install libpq "
            "and add /opt/homebrew/opt/libpq/bin to PATH."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import frontend curatedNotes JSON into Neon Postgres using safe batched psql CSV imports."
    )

    parser.add_argument(
        "seed_json",
        help="Path to technical-notes-seed JSON file exported from frontend curatedNotes.",
    )

    parser.add_argument(
        "--conn",
        default=os.environ.get("NEON_DATABASE_URL") or os.environ.get("DATABASE_URL") or "postgresql://neondb_owner:npg_iA9KQLq6ZMDw@ep-weathered-lake-atd5m4fr.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require",
        help="Neon unpooled Postgres connection string. Prefer setting NEON_DATABASE_URL env var.",
    )

    parser.add_argument(
        "--work-dir",
        default=".neon_import_batches",
        help="Temporary folder where batched CSV files will be generated.",
    )

    parser.add_argument(
        "--topic-batch-size",
        type=int,
        default=5,
        help="Number of large topic rows per CSV batch.",
    )

    parser.add_argument(
        "--section-batch-size",
        type=int,
        default=250,
        help="Number of section rows per CSV batch.",
    )

    parser.add_argument(
        "--source-link-batch-size",
        type=int,
        default=500,
        help="Number of topic-source link rows per CSV batch.",
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=4,
        help="Retries per psql import command.",
    )

    parser.add_argument(
        "--clean",
        action="store_true",
        help="Truncate existing notes-related tables before import.",
    )

    parser.add_argument(
        "--skip-search-refresh",
        action="store_true",
        help="Skip refresh_topic_search_vectors() after import.",
    )

    args = parser.parse_args()

    if not args.conn:
        print("Missing connection string. Set NEON_DATABASE_URL or pass --conn.", file=sys.stderr)
        sys.exit(1)

    check_psql_exists()

    seed_path = Path(args.seed_json).expanduser().resolve()
    work_dir = Path(args.work_dir).expanduser().resolve()

    if not seed_path.exists():
        print(f"Seed JSON not found: {seed_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading seed JSON: {seed_path}")
    rows = build_rows(seed_path)

    print("\nPrepared rows:")
    for name, table_rows in rows.items():
        print(f"  {name}: {len(table_rows)}")

    work_dir.mkdir(parents=True, exist_ok=True)

    groups_csv = work_dir / "01_groups.csv"
    domains_csv = work_dir / "02_domains.csv"
    source_files_csv = work_dir / "05_source_files.csv"

    write_csv(groups_csv, GROUP_COLUMNS, rows["groups"])
    write_csv(domains_csv, DOMAIN_COLUMNS, rows["domains"])
    write_csv(source_files_csv, SOURCE_FILE_COLUMNS, rows["source_files"])

    topic_files = write_batched_csvs(
        work_dir,
        "03_topics",
        TOPIC_COLUMNS,
        rows["topics"],
        args.topic_batch_size,
    )

    section_files = write_batched_csvs(
        work_dir,
        "04_topic_sections",
        SECTION_COLUMNS,
        rows["topic_sections"],
        args.section_batch_size,
    )

    topic_source_link_files = write_batched_csvs(
        work_dir,
        "06_topic_source_links",
        TOPIC_SOURCE_LINK_COLUMNS,
        rows["topic_source_links"],
        args.source_link_batch_size,
    )

    print(f"\nGenerated CSV batches in: {work_dir}")

    if args.clean:
        print("\nCleaning existing DB data...")
        clean_database(args.conn, args.retries)

    print("\nImporting small lookup tables...")
    copy_csv(args.conn, "groups", GROUP_COLUMNS, groups_csv, args.retries)
    copy_csv(args.conn, "domains", DOMAIN_COLUMNS, domains_csv, args.retries)

    print("\nImporting topic batches...")
    for index, file_path in enumerate(topic_files, start=1):
        print(f"\nTopic batch {index}/{len(topic_files)}")
        copy_csv(args.conn, "topics", TOPIC_COLUMNS, file_path, args.retries)

    print("\nImporting section batches...")
    for index, file_path in enumerate(section_files, start=1):
        print(f"\nSection batch {index}/{len(section_files)}")
        copy_csv(args.conn, "topic_sections", SECTION_COLUMNS, file_path, args.retries)

    print("\nImporting source files...")
    copy_csv(args.conn, "source_files", SOURCE_FILE_COLUMNS, source_files_csv, args.retries)

    print("\nImporting topic-source links...")
    for index, file_path in enumerate(topic_source_link_files, start=1):
        print(f"\nTopic-source link batch {index}/{len(topic_source_link_files)}")
        copy_csv(
            args.conn,
            "topic_source_links",
            TOPIC_SOURCE_LINK_COLUMNS,
            file_path,
            args.retries,
        )

    if not args.skip_search_refresh:
        print("\nRefreshing search vectors...")
        refresh_search(args.conn, args.retries)

    print("\nVerifying counts...")
    verify_counts(args.conn, args.retries)

    print("\n✅ Import completed successfully.")


if __name__ == "__main__":
    main()
