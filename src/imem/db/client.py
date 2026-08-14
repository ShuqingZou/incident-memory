from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from imem.config import settings


@lru_cache(maxsize=1)
def get_db() -> Database:
    return MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)[
        settings.mongodb_db
    ]
