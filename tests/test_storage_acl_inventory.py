"""Regression tests for the installed production storage ACL allowlist."""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "storage_production_runner_acl_test",
    ROOT / "scripts/storage_production_migration.py",
)
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)

OWNER = "vervfy_storage_lifecycle_owner"
EXECUTOR = "vervfy_storage_cleanup"
WORKER = "storage_cleanup_worker"

OWNER_FUNCTIONS = (
    "guard_namespace()",
    "validate_namespace(p_id uuid, p_environment text, p_endpoint text, p_bucket text)",
    "_has_references(p_path text)",
    "_queue(p_object uuid, p_actor text)",
    "reserve_object(p_kind text, p_extension text)",
    "advance_upload(p_object uuid, p_token uuid, p_next text)",
    "request_cleanup(p_object uuid)",
    "guard_references()",
    "retire_candidate(p_object uuid)",
    "claim_cleanup(p_object uuid)",
    "claim_next_cleanup()",
    "complete_cleanup(p_object uuid, p_token uuid)",
    "retry_cleanup(p_object uuid, p_token uuid, p_error_code text)",
)
EXECUTOR_FUNCTIONS = (
    "claim_cleanup(p_object uuid)",
    "claim_next_cleanup()",
    "complete_cleanup(p_object uuid, p_token uuid)",
    "retire_candidate(p_object uuid)",
    "retry_cleanup(p_object uuid, p_token uuid, p_error_code text)",
    "validate_namespace(p_id uuid, p_environment text, p_endpoint text, p_bucket text)",
)


def acl(role, kind, name, privilege):
    return SimpleNamespace(
        role_name=role,
        object_type=kind,
        object_name=name,
        privilege_type=privilege,
        is_grantable=False,
    )


def inventory_connection(
    *,
    extra_acl=(),
    extra_owner=(),
    defaults=(),
    extra_effective_relation=(),
    extra_effective_column=(),
    extra_effective_sequence=(),
    extra_effective_function=(),
    unsafe_schema=None,
):
    rows = [
        acl(OWNER, "SCHEMA", "vervfy_storage", "USAGE"),
        acl(OWNER, "SCHEMA", "public", "USAGE"),
        acl(EXECUTOR, "SCHEMA", "vervfy_storage", "USAGE"),
    ]
    for table, privileges in {
        "vervfy_storage.namespaces": ("SELECT",),
        "vervfy_storage.objects": ("SELECT", "INSERT", "UPDATE"),
        "vervfy_storage.cleanup_jobs": ("SELECT", "INSERT", "UPDATE"),
    }.items():
        rows.extend(acl(OWNER, "TABLE", table, p) for p in privileges)
    for table, column in (
        ("public.users", "id"),
        ("public.tracks", "storage_path"),
        ("public.tracks", "cover_path"),
        ("public.artist_photos", "storage_path"),
        ("public.upload_jobs", "storage_path"),
    ):
        rows.append(acl(OWNER, "COLUMN", f"{table}.{column}", "SELECT"))
    rows.extend(
        acl(OWNER, "FUNCTION", f"vervfy_storage.{signature}", "EXECUTE")
        for signature in OWNER_FUNCTIONS
    )
    rows.extend(
        acl(EXECUTOR, "FUNCTION", f"vervfy_storage.{signature}", "EXECUTE")
        for signature in EXECUTOR_FUNCTIONS
    )
    rows.extend(extra_acl)

    ownership = [
        SimpleNamespace(
            role_name=OWNER,
            object_type="FUNCTION",
            object_name=f"vervfy_storage.{signature}",
        )
        for signature in OWNER_FUNCTIONS
    ]
    ownership.extend(extra_owner)

    first = MagicMock()
    first.all.return_value = rows
    effective_relations = MagicMock()
    effective_relations.all.return_value = list(extra_effective_relation)
    effective_columns = MagicMock()
    effective_columns.all.return_value = list(extra_effective_column)
    effective_sequences = MagicMock()
    effective_sequences.all.return_value = list(extra_effective_sequence)
    effective_functions = MagicMock()
    effective_functions.all.return_value = list(extra_effective_function)
    schema_create = MagicMock()
    schema_create.first.return_value = unsafe_schema
    owned = MagicMock()
    owned.all.return_value = ownership
    default_acls = MagicMock()
    default_acls.scalars.return_value.all.return_value = list(defaults)

    connection = MagicMock()
    connection.execute.side_effect = [
        first, effective_relations, effective_columns, effective_sequences,
        effective_functions, schema_create, owned, default_acls,
    ]
    return connection


def check(connection):
    RUNNER._check_storage_acl_inventory(
        connection, owner=OWNER, executor=EXECUTOR, worker=WORKER
    )


class StorageAclInventoryTests(unittest.TestCase):
    def test_accepts_exact_reviewed_storage_acl_inventory(self):
        check(inventory_connection())

    def test_rejects_unexpected_direct_table_grant(self):
        connection = inventory_connection(
            extra_acl=(acl(EXECUTOR, "TABLE", "public.users", "DELETE"),)
        )
        with self.assertRaisesRegex(
            RuntimeError, "Unexpected direct storage capability ACL"
        ):
            check(connection)

    def test_rejects_grantable_storage_permission(self):
        entry = acl(OWNER, "TABLE", "vervfy_storage.objects", "UPDATE")
        entry.is_grantable = True
        with self.assertRaisesRegex(
            RuntimeError, "Unexpected direct storage capability ACL"
        ):
            check(inventory_connection(extra_acl=(entry,)))

    def test_rejects_unexpected_capability_object_ownership(self):
        extra = SimpleNamespace(
            role_name=OWNER,
            object_type="TABLE",
            object_name="public.users",
        )
        with self.assertRaisesRegex(RuntimeError, "unexpectedly owns"):
            check(inventory_connection(extra_owner=(extra,)))

    def test_rejects_default_acl_for_capability_role(self):
        with self.assertRaisesRegex(RuntimeError, "default ACLs"):
            check(inventory_connection(defaults=(OWNER,)))

    def test_rejects_unexpected_effective_public_relation_privilege(self):
        extra = SimpleNamespace(
            role_name=EXECUTOR,
            object_name="public.users",
            privilege_type="SELECT",
        )
        with self.assertRaisesRegex(RuntimeError, "Unexpected effective storage"):
            check(inventory_connection(extra_effective_relation=(extra,)))

    def test_rejects_unexpected_effective_function_privilege(self):
        extra = SimpleNamespace(
            role_name=WORKER,
            object_name="public.unreviewed_function()",
        )
        with self.assertRaisesRegex(RuntimeError, "Unexpected effective storage capability function"):
            check(inventory_connection(extra_effective_function=(extra,)))

    def test_rejects_effective_schema_create(self):
        extra = SimpleNamespace(rolname=OWNER, nspname="public")
        with self.assertRaisesRegex(RuntimeError, "schema CREATE"):
            check(inventory_connection(unsafe_schema=extra))

    def test_rejects_unexpected_effective_column_privilege(self):
        extra = SimpleNamespace(
            role_name=OWNER,
            object_name="public.tracks.title",
            privilege_type="SELECT",
        )
        with self.assertRaisesRegex(RuntimeError, "column privileges"):
            check(inventory_connection(extra_effective_column=(extra,)))

    def test_rejects_effective_sequence_privilege(self):
        extra = SimpleNamespace(
            role_name=OWNER,
            object_name="public.users_id_seq",
            privilege_type="USAGE",
        )
        with self.assertRaisesRegex(RuntimeError, "sequence privileges"):
            check(inventory_connection(extra_effective_sequence=(extra,)))

