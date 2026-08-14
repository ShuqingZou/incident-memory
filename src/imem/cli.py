import typer
from rich.console import Console
from rich.table import Table

from imem.config import settings
from imem.db.bootstrap import bootstrap as _bootstrap
from imem.db.client import get_db

app = typer.Typer(help="incident-memory: an on-call agent that learns from being paged")
console = Console()


@app.command()
def bootstrap(drop: bool = typer.Option(False, help="drop all collections first")):
    """Create collections and search indexes. Idempotent."""
    _bootstrap(drop=drop)


@app.command()
def status():
    """Show what currently exists in the database."""
    db = get_db()
    console.print(f"[dim]{settings.mongodb_uri} -> {settings.mongodb_db}[/dim]\n")

    t = Table("collection", "documents")
    for name in sorted(db.list_collection_names()):
        t.add_row(name, str(db[name].count_documents({})))
    console.print(t)

    if "incidents" in db.list_collection_names():
        idx = Table("search index", "status")
        for ix in db.incidents.list_search_indexes():
            idx.add_row(ix["name"], ix.get("status", "?"))
        console.print(idx)


@app.command()
def reset(keep_telemetry: bool = typer.Option(False)):
    """Wipe memory and runs. Keeps search indexes."""
    db = get_db()
    for c in ["incidents", "agent_runs", "alerts", "ground_truth"]:
        db[c].delete_many({})
    if not keep_telemetry:
        db.telemetry.delete_many({})
    console.print("[green]reset complete[/green]")


if __name__ == "__main__":
    app()
