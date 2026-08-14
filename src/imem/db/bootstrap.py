import time

from pymongo.errors import CollectionInvalid
from pymongo.operations import SearchIndexModel

from imem.config import settings
from imem.db.client import get_db

VECTOR_INDEX = "incidents_vector"
TEXT_INDEX = "incidents_text"

COLLECTIONS = ["telemetry", "incidents", "agent_runs",
               "deploys", "alerts", "ground_truth"]


def bootstrap(drop: bool = False) -> None:
    db = get_db()

    if drop:
        for c in COLLECTIONS:
            db.drop_collection(c)
        print("dropped all collections")

    try:
        db.create_collection(
            "telemetry",
            timeseries={"timeField": "ts", "metaField": "meta",
                        "granularity": "seconds"},
            expireAfterSeconds=60 * 60 * 24 * 30,
        )
        print("created telemetry (time-series)")
    except CollectionInvalid:
        print("telemetry exists")

    db.deploys.create_index([("service", 1), ("ts", -1)])
    db.agent_runs.create_index([("alert_id", 1), ("created_at", -1)])
    db.incidents.create_index([("root_cause", 1)])
    db.ground_truth.create_index([("alert_id", 1)], unique=True)
    print("regular indexes ok")

    # mongot can stall building against a fully empty collection
    placeholder = db.incidents.count_documents({}) == 0
    if placeholder:
        db.incidents.insert_one({"_id": "__placeholder__",
                                 "situation_embedding": [0.0] * settings.embed_dims})

    _ensure(db.incidents, SearchIndexModel(
        name=VECTOR_INDEX, type="vectorSearch",
        definition={"fields": [
            {"type": "vector", "path": "situation_embedding",
             "numDimensions": settings.embed_dims, "similarity": "cosine"},
            {"type": "filter", "path": "signal"},
            {"type": "filter", "path": "service_tier"},
            {"type": "filter", "path": "deploy_adjacent"},
        ]},
    ))

    _ensure(db.incidents, SearchIndexModel(
        name=TEXT_INDEX, type="search",
        definition={"mappings": {"dynamic": False, "fields": {
            "service": {"type": "string"},
            "root_cause": {"type": "string"},
            "key_observations": {"type": "string"},
        }}},
    ))

    _wait_ready(db.incidents, [VECTOR_INDEX, TEXT_INDEX])

    if placeholder:
        db.incidents.delete_one({"_id": "__placeholder__"})
        print("removed placeholder")


def _ensure(coll, model: SearchIndexModel) -> None:
    name = model.document["name"]
    if name in {ix["name"] for ix in coll.list_search_indexes()}:
        print(f"{name} exists")
        return
    coll.create_search_index(model=model)
    print(f"creating {name}...")


def _wait_ready(coll, names: list[str], timeout: int = 300) -> None:
    deadline = time.time() + timeout
    status: dict = {}
    while time.time() < deadline:
        status = {ix["name"]: ix.get("status")
                  for ix in coll.list_search_indexes() if ix["name"] in names}
        if len(status) == len(names) and all(s == "READY" for s in status.values()):
            print("search indexes READY")
            return
        print(f"  waiting: {status}")
        time.sleep(5)
    raise TimeoutError(f"indexes not ready: {status}")
