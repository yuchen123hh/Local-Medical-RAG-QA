from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
import sqlite3
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from langchain_core.documents import Document  # noqa: E402

from app.rag.vector_store import VectorStoreService  # noqa: E402


CARD_PATTERN = re.compile(r"(?=^### MED-\d{5,6}｜)", re.MULTILINE)
TITLE_PATTERN = re.compile(r"^### (?P<record_id>MED-\d{5,6})｜(?P<system>[^｜]+)｜(?P<disease>[^｜]+)｜(?P<scenario>.+)$")


def parse_cards(path: Path, user_id: str, corpus_name: str) -> tuple[str, list[Document]]:
    text = path.read_text(encoding="utf-8")
    md5 = hashlib.md5(text.encode("utf-8")).hexdigest()
    chunks = [chunk.strip() for chunk in CARD_PATTERN.split(text) if chunk.strip().startswith("### MED-")]

    documents: list[Document] = []
    for index, chunk in enumerate(chunks):
        title = chunk.splitlines()[0]
        match = TITLE_PATTERN.match(title)
        metadata = {
            "source": str(path),
            "filename": path.name,
            "original_filename": corpus_name,
            "user_id": user_id,
            "md5": md5,
            "card_index": index,
            "import_mode": "medical_card",
        }
        if match:
            metadata.update(match.groupdict())
        documents.append(Document(page_content=chunk, metadata=metadata))

    return md5, documents


def iter_markdown_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.glob("*.md"))


def load_existing_record_ids(store: VectorStoreService, user_id: str) -> set[str]:
    existing_record_ids: set[str] = set()

    db_path = BACKEND_DIR / "data" / "chromadb" / "chroma.sqlite3"
    if not db_path.exists():
        return existing_record_ids

    query = """
        SELECT DISTINCT em_record.string_value
        FROM embeddings e
        JOIN embedding_metadata em_user
          ON e.id = em_user.id
         AND em_user.key = 'user_id'
         AND em_user.string_value = ?
        JOIN embedding_metadata em_record
          ON e.id = em_record.id
         AND em_record.key = 'record_id'
        WHERE em_record.string_value IS NOT NULL
    """

    with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=30) as con:
        cur = con.cursor()
        for row in cur.execute(query, (user_id,)):
            record_id = row[0]
            if record_id:
                existing_record_ids.add(record_id)
    return existing_record_ids


async def import_batch(store: VectorStoreService, batch: list[Document], executor: ThreadPoolExecutor) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(executor, store.vectors_store.add_documents, batch)


async def import_files(
    input_path: Path,
    user_id: str,
    corpus_name: str,
    batch_size: int,
    replace: bool,
    concurrency: int,
    target_total: int | None,
) -> None:
    store = VectorStoreService()

    if replace:
        await store.delete_user_documents(user_id)
        existing_record_ids: set[str] = set()
    else:
        existing_record_ids = load_existing_record_ids(store, user_id)

    files = iter_markdown_files(input_path)
    if not files:
        raise SystemExit(f"No Markdown files found: {input_path}")

    total_cards = len(existing_record_ids)
    initial_total = total_cards
    started = time.time()
    executor = ThreadPoolExecutor(max_workers=concurrency)

    if target_total is not None and total_cards >= target_total:
        print(f"Target total {target_total} already reached for user {user_id}.")
        executor.shutdown(wait=True)
        return

    async def flush_pending(pending: list[tuple[asyncio.Task, list[str]]]) -> tuple[int, list[str]]:
        if not pending:
            return 0, []
        await asyncio.gather(*(task for task, _ in pending))
        imported = 0
        new_record_ids: list[str] = []
        for _, record_ids in pending:
            imported += len(record_ids)
            new_record_ids.extend(record_ids)
        pending.clear()
        return imported, new_record_ids

    try:
        for file_index, path in enumerate(files, start=1):
            if target_total is not None and total_cards >= target_total:
                print(f"Reached target total {target_total}, stopping.")
                break

            md5, documents = parse_cards(path, user_id, corpus_name)
            if not documents:
                print(f"[{file_index}/{len(files)}] skip empty file: {path.name}")
                continue

            file_record_ids = [
                doc.metadata.get("record_id")
                for doc in documents
                if isinstance(doc.metadata, dict) and doc.metadata.get("record_id")
            ]
            missing_documents = [
                doc for doc in documents
                if not isinstance(doc.metadata, dict)
                or doc.metadata.get("record_id") not in existing_record_ids
            ]

            if not missing_documents:
                if not await store.check_md5_hex(md5, user_id):
                    await store.save_md5_hex(md5, corpus_name, corpus_name, user_id)
                print(f"[{file_index}/{len(files)}] skip already imported file: {path.name}")
                continue

            print(
                f"[{file_index}/{len(files)}] importing {path.name}: "
                f"{len(missing_documents)} new cards"
            )
            pending: list[tuple[asyncio.Task, list[str]]] = []
            imported_in_file = 0
            for start in range(0, len(missing_documents), batch_size):
                if target_total is not None and total_cards >= target_total:
                    break

                batch = missing_documents[start:start + batch_size]
                if target_total is not None:
                    remaining = target_total - total_cards
                    if remaining <= 0:
                        break
                    batch = batch[:remaining]

                batch_record_ids = [
                    doc.metadata.get("record_id")
                    for doc in batch
                    if isinstance(doc.metadata, dict) and doc.metadata.get("record_id")
                ]
                pending.append((asyncio.create_task(import_batch(store, batch, executor)), batch_record_ids))
                if len(pending) >= concurrency:
                    imported_now, new_record_ids = await flush_pending(pending)
                    total_cards += imported_now
                    imported_in_file += imported_now
                    existing_record_ids.update(new_record_ids)
                    print(
                        f"  - {path.name}: {imported_in_file}/{len(missing_documents)} new cards, "
                        f"total={total_cards}",
                        flush=True,
                    )

            if pending:
                imported_now, new_record_ids = await flush_pending(pending)
                total_cards += imported_now
                imported_in_file += imported_now
                existing_record_ids.update(new_record_ids)
                print(
                    f"  - {path.name}: {imported_in_file}/{len(missing_documents)} new cards, "
                    f"total={total_cards}",
                    flush=True,
                )

            if set(file_record_ids).issubset(existing_record_ids):
                if not await store.check_md5_hex(md5, user_id):
                    await store.save_md5_hex(md5, corpus_name, corpus_name, user_id)
            else:
                print(f"  - {path.name}: partial import, md5 not saved yet")

            if target_total is not None and total_cards >= target_total:
                print(f"Reached target total {target_total}, stopping.")
                break
    finally:
        executor.shutdown(wait=True)

    elapsed = round(time.time() - started, 2)
    imported_new = total_cards - initial_total
    print(
        f"Imported {imported_new} new cards; total for user {user_id} is {total_cards} "
        f"from {len(files)} files as '{corpus_name}' in {elapsed}s"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import MED knowledge cards into Chroma without re-splitting.")
    parser.add_argument("--input", type=Path, required=True, help="Markdown file or directory to import.")
    parser.add_argument("--user-id", required=True, help="Target user id stored in document metadata.")
    parser.add_argument("--corpus-name", default="medical_rag_cards.md", help="Document name shown in knowledge list.")
    parser.add_argument("--batch-size", type=int, default=100, help="Chroma add_documents batch size.")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrent Chroma add_documents workers.")
    parser.add_argument("--replace", action="store_true", help="Delete existing document with the same corpus name first.")
    parser.add_argument("--target-total", type=int, default=None, help="Stop after the user's total cards reach this number.")
    args = parser.parse_args()

    input_path = args.input if args.input.is_absolute() else PROJECT_ROOT / args.input
    os.chdir(BACKEND_DIR)
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be greater than zero")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be greater than zero")

    asyncio.run(
        import_files(
            input_path.resolve(),
            args.user_id,
            args.corpus_name,
            args.batch_size,
            args.replace,
            args.concurrency,
            args.target_total,
        )
    )


if __name__ == "__main__":
    main()
