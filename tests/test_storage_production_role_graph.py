"""Regression tests for storage production role-graph preflight gaps vs 0029."""

from __future__ import annotations

import contextlib
import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from scripts import storage_production_migration as runner


def _role(
    *,
    oid: int,
    name: str,
    login: bool = False,
    inherit: bool = False,
    superuser: bool = False,
    bypass_rls: bool = False,
    createdb: bool = False,
    createrole: bool = False,
    replication: bool = False,
):
    return SimpleNamespace(
        oid=oid,
        rolname=name,
        rolcanlogin=login,
        rolinherit=inherit,
        rolsuper=superuser,
        rolbypassrls=bypass_rls,
        rolcreatedb=createdb,
        rolcreaterole=createrole,
        rolreplication=replication,
    )


def _member(member: int, *, inherit: bool, set_option: bool, admin: bool):
    return SimpleNamespace(
        member=member,
        inherit_option=inherit,
        set_option=set_option,
        admin_option=admin,
    )


def _result(rows=None, *, scalar=None, first=None):
    result = MagicMock()
    result.all.return_value = list(rows or ())
    result.first.return_value = first
    result.scalar_one.return_value = scalar
    result.scalar_one_or_none.return_value = scalar
    return result


def _capability_rows():
    return [
        _role(oid=10, name="vervfy_storage_lifecycle_owner"),
        _role(oid=20, name="vervfy_storage_cleanup"),
        _role(oid=30, name="storage_cleanup_worker", login=True),
    ]


def _runtime_row(*, inherit=True):
    return _role(oid=40, name="app_runtime", login=True, inherit=inherit)


def test_block_role_graph_is_categorized_and_credential_free():
    with pytest.raises(runner.MigrationBlocked) as raised:
        runner._block_role_graph(
            runner.ROLE_GRAPH_CATEGORY_APP_RUNTIME_ATTRIBUTES,
            "app_runtime must be LOGIN INHERIT without elevated privileges",
        )
    message = str(raised.value)
    assert message.startswith("storage_role_graph category=app_runtime_attributes;")
    assert "postgresql://" not in message
    assert "sslrootcert" not in message
    assert "password" not in message.lower()


def test_app_runtime_noinherit_is_blocked():
    migration = runner._load_storage_lifecycle_migration()
    connection = MagicMock()
    connection.execute.return_value = _result(first=_runtime_row(inherit=False))

    with pytest.raises(runner.MigrationBlocked) as raised:
        runner._check_app_runtime_attributes(connection, migration)

    assert "category=app_runtime_attributes" in str(raised.value)


def test_app_runtime_missing_is_blocked():
    migration = runner._load_storage_lifecycle_migration()
    connection = MagicMock()
    connection.execute.return_value = _result(first=None)

    with pytest.raises(runner.MigrationBlocked) as raised:
        runner._check_app_runtime_attributes(connection, migration)

    assert "category=app_runtime_attributes" in str(raised.value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"superuser": True},
        {"bypass_rls": True},
        {"createdb": True},
        {"createrole": True},
        {"replication": True},
        {"login": False},
    ],
)
def test_app_runtime_elevated_or_nologin_is_blocked(kwargs):
    migration = runner._load_storage_lifecycle_migration()
    connection = MagicMock()
    defaults = {
        "oid": 40,
        "name": "app_runtime",
        "login": True,
        "inherit": True,
    }
    defaults.update(kwargs)
    connection.execute.return_value = _result(first=_role(**defaults))

    with pytest.raises(runner.MigrationBlocked) as raised:
        runner._check_app_runtime_attributes(connection, migration)

    assert "category=app_runtime_attributes" in str(raised.value)


def test_app_runtime_login_inherit_is_accepted():
    migration = runner._load_storage_lifecycle_migration()
    connection = MagicMock()
    runtime = _runtime_row()
    connection.execute.return_value = _result(first=runtime)

    assert runner._check_app_runtime_attributes(connection, migration) is runtime


def test_storage_membership_options_reject_postgres_set_on_owner():
    """Preflight used to accept postgres SET; migration 0029 requires ADMIN only."""
    migration = runner._load_storage_lifecycle_migration()
    connection = MagicMock()
    owner_oid, executor_oid, worker_oid = 10, 20, 30
    migrator_oid, postgres_oid = 99, 1

    def execute(statement, params=None):
        sql = str(statement)
        if "current_user::regrole::oid" in sql:
            return _result(scalar=migrator_oid)
        if "rolname = 'postgres'" in sql or "rolname='postgres'" in sql:
            return _result(scalar=postgres_oid)
        if params and params.get("owner") == owner_oid:
            return _result(
                [
                    _member(migrator_oid, inherit=False, set_option=True, admin=False),
                    # Optional edge historically accepted by assert_role_memberships.
                    _member(postgres_oid, inherit=False, set_option=True, admin=False),
                ]
            )
        if params and params.get("executor") == executor_oid:
            return _result(
                [_member(worker_oid, inherit=True, set_option=False, admin=False)]
            )
        raise AssertionError(f"unexpected SQL: {sql} {params}")

    connection.execute.side_effect = execute

    with pytest.raises(runner.MigrationBlocked) as raised:
        runner._check_storage_membership_options(
            connection,
            migration,
            owner_oid=owner_oid,
            executor_oid=executor_oid,
            worker_oid=worker_oid,
        )

    message = str(raised.value)
    assert "category=storage_membership_options" in message
    assert "postgresql://" not in message


def test_storage_membership_options_reject_wrong_executor_options():
    migration = runner._load_storage_lifecycle_migration()
    connection = MagicMock()
    owner_oid, executor_oid, worker_oid = 10, 20, 30
    migrator_oid, postgres_oid = 99, 1

    def execute(statement, params=None):
        sql = str(statement)
        if "current_user::regrole::oid" in sql:
            return _result(scalar=migrator_oid)
        if "rolname = 'postgres'" in sql or "rolname='postgres'" in sql:
            return _result(scalar=postgres_oid)
        if params and params.get("owner") == owner_oid:
            return _result(
                [_member(migrator_oid, inherit=False, set_option=True, admin=False)]
            )
        if params and params.get("executor") == executor_oid:
            # Worker must inherit executor; SET TRUE is rejected by 0029.
            return _result(
                [_member(worker_oid, inherit=True, set_option=True, admin=False)]
            )
        raise AssertionError(f"unexpected SQL: {sql} {params}")

    connection.execute.side_effect = execute

    with pytest.raises(runner.MigrationBlocked) as raised:
        runner._check_storage_membership_options(
            connection,
            migration,
            owner_oid=owner_oid,
            executor_oid=executor_oid,
            worker_oid=worker_oid,
        )

    assert "category=storage_membership_options" in str(raised.value)


def test_storage_membership_options_accept_inert_postgres_admin():
    migration = runner._load_storage_lifecycle_migration()
    connection = MagicMock()
    owner_oid, executor_oid, worker_oid = 10, 20, 30
    migrator_oid, postgres_oid = 99, 1

    def execute(statement, params=None):
        sql = str(statement)
        if "current_user::regrole::oid" in sql:
            return _result(scalar=migrator_oid)
        if "rolname = 'postgres'" in sql or "rolname='postgres'" in sql:
            return _result(scalar=postgres_oid)
        if params and params.get("owner") == owner_oid:
            return _result(
                [
                    _member(migrator_oid, inherit=False, set_option=True, admin=False),
                    _member(postgres_oid, inherit=False, set_option=False, admin=True),
                ]
            )
        if params and params.get("executor") == executor_oid:
            return _result(
                [
                    _member(worker_oid, inherit=True, set_option=False, admin=False),
                    _member(postgres_oid, inherit=False, set_option=False, admin=True),
                ]
            )
        raise AssertionError(f"unexpected SQL: {sql} {params}")

    connection.execute.side_effect = execute
    runner._check_storage_membership_options(
        connection,
        migration,
        owner_oid=owner_oid,
        executor_oid=executor_oid,
        worker_oid=worker_oid,
    )


def test_effective_privilege_inheritance_is_blocked():
    connection = MagicMock()
    connection.execute.return_value = _result(first=(1,))

    with pytest.raises(runner.MigrationBlocked) as raised:
        runner._check_effective_privilege_inheritance(
            connection,
            owner_oid=10,
            executor_oid=20,
            worker_oid=30,
            postgres_oid=40,
        )

    assert "category=effective_privilege_inheritance" in str(raised.value)


def test_effective_privilege_inheritance_passes_when_clean():
    connection = MagicMock()
    connection.execute.return_value = _result(first=None)
    runner._check_effective_privilege_inheritance(
        connection,
        owner_oid=10,
        executor_oid=20,
        worker_oid=30,
        postgres_oid=40,
    )


def test_check_role_graph_detects_app_runtime_membership():
    connection = MagicMock()

    def execute(statement, params=None):
        sql = str(statement)
        if "WHERE rolname IN (:owner, :executor, :worker)" in sql:
            return _result(_capability_rows())
        if "WHERE rolname = :name" in sql:
            return _result(first=_runtime_row())
        return _result()

    connection.execute.side_effect = execute

    def assert_member_memberships(_bind, member_name, _explicit):
        if member_name == runner.APP_RUNTIME:
            raise RuntimeError("app_runtime holds membership")

    with (
        patch("supabase_role_memberships.assert_role_memberships"),
        patch(
            "supabase_role_memberships.assert_member_memberships",
            side_effect=assert_member_memberships,
        ),
        pytest.raises(runner.MigrationBlocked) as raised,
    ):
        runner._check_role_graph(connection, "vervfy_prod_migrator")

    assert "category=app_runtime_memberships" in str(raised.value)


def test_check_role_graph_detects_executor_holding_memberships():
    connection = MagicMock()

    def execute(statement, params=None):
        sql = str(statement)
        if "WHERE rolname IN (:owner, :executor, :worker)" in sql:
            return _result(_capability_rows())
        if "WHERE rolname = :name" in sql:
            return _result(first=_runtime_row())
        return _result()

    connection.execute.side_effect = execute

    def assert_member_memberships(_bind, member_name, _explicit):
        if member_name == "vervfy_storage_cleanup":
            raise RuntimeError("executor holds memberships")

    with (
        patch("supabase_role_memberships.assert_role_memberships"),
        patch(
            "supabase_role_memberships.assert_member_memberships",
            side_effect=assert_member_memberships,
        ),
        pytest.raises(runner.MigrationBlocked) as raised,
    ):
        runner._check_role_graph(connection, "vervfy_prod_migrator")

    assert "category=capability_memberships" in str(raised.value)


def _role_graph_execute(*, effective_hit=False):
    def execute(statement, params=None):
        sql = str(statement)
        if "WHERE rolname IN (:owner, :executor, :worker)" in sql:
            return _result(_capability_rows())
        if "WHERE rolname = :name" in sql:
            return _result(first=_runtime_row())
        # Effective inheritance query also mentions current_user::regrole::oid.
        if "pg_catalog.pg_has_role(r.oid" in sql:
            return _result(first=(1,) if effective_hit else None)
        if "pg_has_role(current_user" in sql:
            return _result(scalar=True)
        if sql.strip() == "SELECT current_user::regrole::oid":
            return _result(scalar=99)
        if "rolname = 'postgres'" in sql or "rolname='postgres'" in sql:
            return _result(scalar=1)
        if params and "owner" in params and "member, inherit_option" in sql:
            return _result(
                [_member(99, inherit=False, set_option=True, admin=False)]
            )
        if params and "executor" in params and "member, inherit_option" in sql:
            return _result(
                [_member(30, inherit=True, set_option=False, admin=False)]
            )
        return _result()

    return execute


def test_check_role_graph_detects_effective_inheritance_gap():
    connection = MagicMock()
    migration = runner._load_storage_lifecycle_migration()
    connection.execute.side_effect = _role_graph_execute(effective_hit=True)

    with (
        patch.object(runner, "_load_storage_lifecycle_migration", return_value=migration),
        patch("supabase_role_memberships.assert_role_memberships"),
        patch("supabase_role_memberships.assert_member_memberships"),
        patch.object(migration, "_fresh_privileges"),
        pytest.raises(runner.MigrationBlocked) as raised,
    ):
        runner._check_role_graph(connection, "vervfy_prod_migrator")

    assert "category=effective_privilege_inheritance" in str(raised.value)


def test_check_role_graph_maps_fresh_privileges_to_category():
    connection = MagicMock()
    migration = runner._load_storage_lifecycle_migration()
    connection.execute.side_effect = _role_graph_execute(effective_hit=False)

    with (
        patch.object(runner, "_load_storage_lifecycle_migration", return_value=migration),
        patch("supabase_role_memberships.assert_role_memberships"),
        patch("supabase_role_memberships.assert_member_memberships"),
        patch.object(
            migration,
            "_fresh_privileges",
            side_effect=RuntimeError("preexisting object privileges"),
        ),
        pytest.raises(runner.MigrationBlocked) as raised,
    ):
        runner._check_role_graph(connection, "vervfy_prod_migrator")

    assert "category=preexisting_privileges" in str(raised.value)


def test_main_prints_categorized_block_without_connection_material():
    stderr = io.StringIO()
    blocked = runner.MigrationBlocked(
        "storage_role_graph category=app_runtime_attributes; "
        "app_runtime must be LOGIN INHERIT without elevated privileges"
    )

    with (
        patch.object(runner, "validate_migration_chain"),
        patch.object(runner, "load_target") as load_target,
        patch.object(runner, "run_check", side_effect=blocked),
        contextlib.redirect_stderr(stderr),
    ):
        load_target.return_value.project_ref = "llxmskxxchpmeavorusj"
        result = runner.main(
            ["check", "--confirm-project-ref", "llxmskxxchpmeavorusj"]
        )

    output = stderr.getvalue()
    assert result == 1
    assert output.startswith("BLOCKED:")
    assert "category=app_runtime_attributes" in output
    assert "postgresql://" not in output
    assert "sslrootcert" not in output
    assert "PASSWORD" not in output
