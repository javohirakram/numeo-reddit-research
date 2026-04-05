"""One-time: create the Pinecone integrated index for Numeo Reddit research.

Run once:

    python scripts/bootstrap_pinecone.py

Requires PINECONE_API_KEY in the environment (or .env). Safe to re-run — it
checks if the index already exists.

Verify Pinecone's current SDK here if this script errors:
https://docs.pinecone.io/guides/inference/understanding-inference
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from pinecone import Pinecone

INDEX_NAME = os.environ.get("PINECONE_INDEX", "numeo-reddit")
CLOUD = "aws"
REGION = "us-east-1"
EMBED_MODEL = "llama-text-embed-v2"


def main() -> int:
    load_dotenv()
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        print("error: PINECONE_API_KEY not set", file=sys.stderr)
        return 1

    pc = Pinecone(api_key=api_key)
    existing = [idx.name for idx in pc.list_indexes()]

    if INDEX_NAME in existing:
        print(f"ok: index '{INDEX_NAME}' already exists")
        return 0

    print(f"creating integrated index '{INDEX_NAME}' on {CLOUD}/{REGION} using {EMBED_MODEL}...")
    pc.create_index_for_model(
        name=INDEX_NAME,
        cloud=CLOUD,
        region=REGION,
        embed={
            "model": EMBED_MODEL,
            "field_map": {"text": "chunk_text"},
        },
    )
    print(f"created: {INDEX_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
