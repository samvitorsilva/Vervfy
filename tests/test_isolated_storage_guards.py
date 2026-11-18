"""Non-database guard tests; these are not evidence of PostgreSQL RLS."""

import uuid
from unittest.mock import Mock, patch

import pytest
import sqlalchemy as sa
from isolated_storage_cleanup import IsolatedCleanupWorker, SyntheticStorage

from scripts.storage_cleanup_worker import CleanupStorageFailure, main
from storage_namespace import NamespaceBinding


def binding():
    return NamespaceBinding(
        uuid.uuid4(), "disposable-test", "https://vervfy.invalid", "synthetic"
    )


def test_rejects_arbitrary_deletion_adapter():
    with pytest.raises(ValueError, match="synthetic"):
        IsolatedCleanupWorker(None, binding(), Mock())


def test_rejects_production_namespace_before_database_access():
    connection = Mock()
    worker = IsolatedCleanupWorker(
        None,
        NamespaceBinding(
            uuid.uuid4(), "production", "https://vervfy.invalid", "synthetic"
        ),
        SyntheticStorage(),
    )
    with pytest.raises(RuntimeError, match="Synthetic namespace"):
        worker.validate(connection)
    connection.execute.assert_not_called()


def test_no_environment_opt_in_no_database_access():
    connection = Mock()
    with patch.dict("os.environ", {}, clear=True):
        worker = IsolatedCleanupWorker(
            sa.create_engine("sqlite://"), binding(), SyntheticStorage()
        )
        with pytest.raises(RuntimeError, match="local-test"):
            worker.validate(connection)
    connection.execute.assert_not_called()


def test_synthetic_absence_and_ambiguous_failure():
    storage = SyntheticStorage({"synthetic": b"only test bytes"})
    storage.failure = "storage_ambiguous"
    with pytest.raises(CleanupStorageFailure):
        storage.delete_if_present("synthetic")
    assert storage.absent("synthetic")
    storage.failure = None
    storage.delete_if_present("synthetic")
    assert storage.absent("synthetic")


def test_entrypoint_remains_disabled():
    with pytest.raises(RuntimeError, match="disabled"):
        main()


@pytest.mark.parametrize("operation", ["claim", "process"])
def test_rejects_configuration_before_opening_connection(operation):
    engine = Mock()
    engine.begin.side_effect = AssertionError("Connection attempted before validation")
    worker = IsolatedCleanupWorker(engine, binding(), SyntheticStorage())
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(RuntimeError, match="local-test"),
    ):
        if operation == "claim":
            worker.claim()
        else:
            worker.process(Mock())
    engine.begin.assert_not_called()


@pytest.mark.parametrize("operation", ["claim", "process"])
def test_rejects_remote_engine_before_checkout(operation):
    import tempfile

    with tempfile.TemporaryDirectory(prefix="vervfy-storage-pg-") as root:
        local_url = sa.URL.create(
            "postgresql+psycopg",
            username="app_runtime",
            database="postgres",
            query={"host": root},
        )
        engine = Mock()
        engine.url = sa.URL.create(
            "postgresql+psycopg",
            username="storage_cleanup_worker",
            host="unapproved.invalid",
            database="postgres",
        )
        worker = IsolatedCleanupWorker(engine, binding(), SyntheticStorage())
        with (
            patch.dict(
                "os.environ",
                {
                    "VERVFY_ENVIRONMENT": "local-test",
                    "VERVFY_STORAGE_BACKEND": "filesystem",
                    "DATABASE_URL": local_url.render_as_string(hide_password=False),
                },
                clear=True,
            ),
            pytest.raises(RuntimeError, match="Unix socket"),
        ):
            if operation == "claim":
                worker.claim()
            else:
                worker.process(Mock())
        engine.begin.assert_not_called()


def test_rejects_replaced_adapter_before_checkout():
    engine = Mock()
    worker = IsolatedCleanupWorker(engine, binding(), SyntheticStorage())
    worker.storage = Mock()
    with pytest.raises(ValueError, match="synthetic"):
        worker.claim()
    engine.begin.assert_not_called()


@pytest.fixture
def process_harness():
    """Stub SQL outcomes to test Python ordering, not database authorization."""
    from unittest.mock import MagicMock

    from scripts.storage_cleanup_worker import CleanupClaim

    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    claim = CleanupClaim(uuid.uuid4(), "synthetic-object", uuid.uuid4())
    storage = SyntheticStorage({claim.path: b"synthetic bytes"})
    worker = IsolatedCleanupWorker(engine, binding(), storage)
    with (
        patch.object(worker, "preflight"),
        patch.object(worker, "validate"),
        patch("isolated_storage_cleanup.ManagedStorageBoundary"),
    ):
        yield worker, connection, claim, storage, engine


@pytest.mark.parametrize("authorized", [False, None])
def test_denied_authorization_never_reaches_storage(process_harness, authorized):
    worker, connection, claim, storage, engine = process_harness
    connection.execute.return_value.scalar_one.return_value = authorized
    with pytest.raises(RuntimeError, match="rejected"):
        worker.process(claim)
    assert storage.calls == []
    assert connection.execute.call_count == 1
    assert engine.begin.return_value.__exit__.call_args.args[0] is RuntimeError


def test_authorization_error_never_reaches_storage(process_harness):
    worker, connection, claim, storage, _ = process_harness
    connection.execute.side_effect = RuntimeError("synthetic database failure")
    with pytest.raises(RuntimeError, match="database failure"):
        worker.process(claim)
    assert storage.calls == []


@pytest.mark.parametrize(
    "failure", ["storage_timeout", "storage_ambiguous", "still_present"]
)
def test_uncertain_deletion_retries_without_completion(process_harness, failure):
    worker, connection, claim, storage, _ = process_harness
    connection.execute.return_value.scalar_one.return_value = True
    storage.failure = failure
    worker.process(claim)
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert len(statements) == 2
    assert "retry_cleanup" in statements[-1]
    assert all("complete_cleanup" not in statement for statement in statements)
    assert connection.execute.call_args.args[1]["token"] == claim.token


def test_absence_precedes_completion(process_harness):
    worker, connection, claim, storage, _ = process_harness

    def execute(statement, parameters):
        if "complete_cleanup" in str(statement):
            assert storage.absent(claim.path)
            assert parameters["token"] == claim.token
        return Mock(scalar_one=Mock(return_value=True))

    connection.execute.side_effect = execute
    worker.process(claim)
    assert "complete_cleanup" in str(connection.execute.call_args.args[0])


@pytest.mark.parametrize("storage_failure", [None, "storage_timeout"])
def test_rejected_persistence_aborts_transaction(process_harness, storage_failure):
    worker, connection, claim, storage, engine = process_harness
    storage.failure = storage_failure
    connection.execute.return_value.scalar_one.side_effect = [True, False]
    with pytest.raises(RuntimeError, match="expired"):
        worker.process(claim)
    assert engine.begin.return_value.__exit__.call_args.args[0] is RuntimeError


def test_unknown_storage_failure_aborts_without_completion(process_harness):
    worker, connection, claim, _storage, engine = process_harness
    connection.execute.return_value.scalar_one.return_value = True
    with (
        patch.object(
            SyntheticStorage, "absent", side_effect=OSError("synthetic error")
        ),
        pytest.raises(OSError),
    ):
        worker.process(claim)
    assert connection.execute.call_count == 1
    assert engine.begin.return_value.__exit__.call_args.args[0] is OSError


def test_rowtype_ddl_reaches_psycopg_without_parameter_processing():
    """Use real SQLAlchemy dispatch and psycopg parsing, without a database."""
    from psycopg import ProgrammingError
    from psycopg._queries import PostgresQuery
    from psycopg.adapt import Transformer
    from test_isolated_storage_cleanup import _install_cleanup_authorizer

    raw = Mock()
    cursor = raw.cursor.return_value
    cursor.description = None
    cursor.rowcount = -1
    seen = []

    def execute(statement, parameters=None):
        query = PostgresQuery(Transformer())
        query.convert(statement, parameters)
        seen.append((statement, parameters, query.query))

    cursor.execute.side_effect = execute
    engine = sa.create_engine("postgresql+psycopg://", creator=lambda: raw)
    try:
        # Only connection initialization is stubbed; DDL dispatch is real.
        with patch.object(engine.dialect, "initialize"), engine.begin() as connection:
            _install_cleanup_authorizer(connection)
        assert len(seen) == 1
        statement, parameters, transmitted = seen[0]
        assert statement.count("%ROWTYPE") == 2
        assert parameters is None
        cursor.execute.assert_called_once_with(statement)
        assert transmitted == statement.encode("utf-8")
        # Control: the former empty-mapping dispatch raises the reported error.
        with pytest.raises(ProgrammingError, match="placeholders"):
            PostgresQuery(Transformer()).convert(statement, {})
    finally:
        engine.dispose()
