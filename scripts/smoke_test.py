"""
Phase 0 smoke test — run this BEFORE writing any project code.

Verifies, against your local Atlas deployment:
  1. connection + server version >= 8.0
  2. time-series collection creation
  3. vectorSearch index builds and reaches READY
  4. text search index builds and reaches READY
  5. $vectorSearch returns sensible neighbours
  6. $rankFusion actually executes

Usage:
    export MONGODB_URI='mongodb://localhost:54587/?directConnection=true'
    python smoke_test.py
"""

import os
import sys
import time

from pymongo import MongoClient
from pymongo.errors import CollectionInvalid, OperationFailure
from pymongo.operations import SearchIndexModel

URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/?directConnection=true")
DB = "imem_smoke"

# Toy 4-dimensional vectors. a1/a2 are near each other; b1 is far away.
DOCS = [
    {"_id": "a1", "text": "latency stepped up while request rate stayed flat",
     "vec": [1.0, 0.1, 0.0, 0.0]},
    {"_id": "a2", "text": "p99 rose sharply, traffic unchanged",
     "vec": [0.9, 0.2, 0.0, 0.1]},
    {"_id": "b1", "text": "certificate handshake failures across all instances",
     "vec": [0.0, 0.0, 1.0, 0.9]},
]


def step(n, msg):
    print(f"[{n}] {msg}")


def wait_ready(coll, names, timeout=300):
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        last = {ix["name"]: ix.get("status") for ix in coll.list_search_indexes()
                if ix["name"] in names}
        if len(last) == len(names) and all(s == "READY" for s in last.values()):
            return True
        print(f"      waiting: {last}")
        time.sleep(5)
    print(f"      TIMEOUT, last status: {last}")
    return False


def main():
    print(f"connecting to {URI}\n")
    client = MongoClient(URI, serverSelectionTimeoutMS=5000)

    # 1 -- connection and version
    version = client.admin.command("buildInfo")["version"]
    major, minor = (int(x) for x in version.split(".")[:2])
    step(1, f"connected, MongoDB {version}")
    if (major, minor) < (8, 0):
        sys.exit("   FAIL: need 8.0+ for $rankFusion")
    print("      OK: >= 8.0\n")

    db = client[DB]
    db.drop_collection("ts_probe")
    db.drop_collection("vec_probe")

    # 2 -- time-series collection
    try:
        db.create_collection(
            "ts_probe",
            timeseries={"timeField": "ts", "metaField": "meta",
                        "granularity": "seconds"},
        )
        step(2, "time-series collection created")
    except CollectionInvalid:
        step(2, "time-series collection already exists")
    from datetime import datetime, timezone
    db.ts_probe.insert_one({"ts": datetime.now(timezone.utc),
                            "meta": {"service": "checkout", "metric": "latency_p99"},
                            "v": 123.4})
    assert db.ts_probe.count_documents({}) == 1
    print("      OK: wrote and read back a measurement\n")

    # 3 -- insert docs BEFORE building indexes (some versions won't
    #      build against an empty collection)
    db.vec_probe.insert_many(DOCS)
    step(3, f"inserted {len(DOCS)} probe documents")

    db.vec_probe.create_search_index(model=SearchIndexModel(
        name="probe_vector", type="vectorSearch",
        definition={"fields": [
            {"type": "vector", "path": "vec",
             "numDimensions": 4, "similarity": "cosine"},
        ]},
    ))
    db.vec_probe.create_search_index(model=SearchIndexModel(
        name="probe_text", type="search",
        definition={"mappings": {"dynamic": False,
                                 "fields": {"text": {"type": "string"}}}},
    ))
    print("      index builds submitted (this takes 30-90s locally)")
    if not wait_ready(db.vec_probe, ["probe_vector", "probe_text"]):
        sys.exit("   FAIL: search indexes never reached READY. "
                 "Check that mongot is running: `docker ps` should show "
                 "the Atlas local container.")
    print("      OK: both indexes READY\n")

    # 4 -- vector search
    step(4, "running $vectorSearch")
    hits = list(db.vec_probe.aggregate([
        {"$vectorSearch": {"index": "probe_vector", "path": "vec",
                           "queryVector": [1.0, 0.0, 0.0, 0.0],
                           "numCandidates": 10, "limit": 3}},
        {"$project": {"_id": 1, "score": {"$meta": "vectorSearchScore"}}},
    ]))
    print(f"      results: {[(h['_id'], round(h['score'], 3)) for h in hits]}")
    if not hits or hits[0]["_id"] not in ("a1", "a2"):
        sys.exit("   FAIL: nearest neighbour should be a1 or a2")
    print("      OK: semantically near docs ranked first\n")

    # 5 -- rank fusion
    step(5, "running $rankFusion")
    try:
        fused = list(db.vec_probe.aggregate([
            {"$rankFusion": {
                "input": {"pipelines": {
                    "semantic": [
                        {"$vectorSearch": {"index": "probe_vector", "path": "vec",
                                           "queryVector": [1.0, 0.0, 0.0, 0.0],
                                           "numCandidates": 10, "limit": 3}},
                    ],
                    "lexical": [
                        {"$search": {"index": "probe_text",
                                     "text": {"query": "latency rate",
                                              "path": "text"}}},
                        {"$limit": 3},
                    ],
                }},
                "combination": {"weights": {"semantic": 0.7, "lexical": 0.3}},
            }},
            {"$limit": 3},
            {"$project": {"_id": 1, "text": 1}},
        ]))
    except OperationFailure as e:
        sys.exit(f"   FAIL: $rankFusion rejected -- {e}\n"
                 f"   Fall back to the Python RRF helper in Phase 4.1.")
    print(f"      fused order: {[f['_id'] for f in fused]}")
    print("      OK: hybrid search works\n")

    client.drop_database(DB)
    print("all checks passed. local Atlas is ready for the project.")


if __name__ == "__main__":
    main()