"""Role-attribute regressions for migration 0029 on Supabase PostgreSQL."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location(
    "storage_lifecycle_migration",
    ROOT / "alembic/versions/0029_storage_lifecycle.py",
)
MIGRATION = module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def role(*, login, inherit, superuser=False, bypass_rls=False,
         createdb=False, createrole=False, replication=False):
    return SimpleNamespace(
        rolcanlogin=login,
        rolinherit=inherit,
        rolsuper=superuser,
        rolbypassrls=bypass_rls,
        rolcreatedb=createdb,
        rolcreaterole=createrole,
        rolreplication=replication,
    )


def test_accepts_existing_supabase_app_runtime_attributes():
    MIGRATION._validate_role_attributes(
        "app_runtime", role(login=True, inherit=True), True
    )


@pytest.mark.parametrize(
    "name,login,inherit",
    [
        (MIGRATION.OWNER, False, False),
        (MIGRATION.EXECUTOR, False, False),
        (MIGRATION.WORKER, True, False),
    ],
)
def test_capability_roles_must_remain_noinherit(name, login, inherit):
    MIGRATION._validate_role_attributes(
        name, role(login=login, inherit=inherit), login
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"login": True, "inherit": True, "superuser": True},
        {"login": True, "inherit": True, "bypass_rls": True},
        {"login": True, "inherit": True, "createdb": True},
        {"login": True, "inherit": True, "createrole": True},
        {"login": True, "inherit": True, "replication": True},
        {"login": True, "inherit": False},
    ],
)
def test_rejects_elevated_or_unexpected_app_runtime_attributes(kwargs):
    with pytest.raises(RuntimeError, match="app_runtime"):
        MIGRATION._validate_role_attributes(
            "app_runtime", role(**kwargs), True
        )


def test_rejects_missing_role():
    with pytest.raises(RuntimeError, match="app_runtime"):
        MIGRATION._validate_role_attributes("app_runtime", None, True)


@pytest.mark.parametrize("owner", [True, False])
def test_accepts_inert_postgres_admin_membership(owner):
    required = SimpleNamespace(member=10, inherit_option=not owner,
                               set_option=owner, admin_option=False)
    postgres = SimpleNamespace(member=20, inherit_option=False,
                               set_option=False, admin_option=True)
    assert MIGRATION._valid_storage_memberships(
        [required, postgres], 10, 20,
        required_inherit=not owner, required_set=owner,
    )


@pytest.mark.parametrize("change", [
    {"inherit_option": True}, {"set_option": True},
    {"admin_option": False}, {"member": 99},
])
def test_rejects_unexpected_admin_membership(change):
    required = SimpleNamespace(member=10, inherit_option=False,
                               set_option=True, admin_option=False)
    admin = {"member": 20, "inherit_option": False,
                 "set_option": False, "admin_option": True}
    admin.update(change)
    assert not MIGRATION._valid_storage_memberships(
        [required, SimpleNamespace(**admin)], 10, 20,
        required_inherit=False, required_set=True,
    )


def test_rejects_extra_membership_and_wrong_required_permissions():
    required = SimpleNamespace(member=10, inherit_option=False,
                               set_option=True, admin_option=False)
    postgres = SimpleNamespace(member=20, inherit_option=False,
                               set_option=False, admin_option=True)
    third = SimpleNamespace(member=30, inherit_option=False,
                            set_option=False, admin_option=False)
    assert not MIGRATION._valid_storage_memberships(
        [required, postgres, third], 10, 20,
        required_inherit=False, required_set=True,
    )
    assert not MIGRATION._valid_storage_memberships(
        [required, postgres], 10, 20,
        required_inherit=True, required_set=False,
    )
