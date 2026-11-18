"""Copy a pinned migration history for offline authorization tests; never execute it."""

import shutil
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def copy_migration_snapshot(source: Path, destination: Path, head: str) -> None:
    config = Config(str(source / "alembic.ini"))
    config.set_main_option("script_location", str(source / "alembic"))
    script = ScriptDirectory.from_config(config)
    versions = destination / "alembic" / "versions"
    versions.mkdir(parents=True)
    for revision in script.walk_revisions(base="base", head=head):
        shutil.copyfile(revision.path, versions / Path(revision.path).name)
    # Resolve against this disposable fixture, never the process working directory.
    (destination / "alembic.ini").write_text(
        "[alembic]\nscript_location = %(here)s/alembic\n", encoding="utf-8"
    )
