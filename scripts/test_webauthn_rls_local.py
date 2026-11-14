"""Rollback-only WebAuthn RLS checks for the isolated local PostgreSQL DB."""

from __future__ import annotations

import hashlib
import os
import sys
import time
import uuid
from getpass import getpass

import psycopg
from psycopg import sql
from psycopg.errors import InsufficientPrivilege

HOST = "127.0.0.1"
PORT = 5433
DATABASE = "vervfy_passkey_e2e"
ROLE = "app_runtime"

TABLES = (
    "webauthn_handles",
    "webauthn_credentials",
    "account_action_intents",
    "account_verification_proofs",
    "account_recovery_codes",
    "account_recovery_states",
    "webauthn_enrollments",
)

TABLE_PRIVILEGES = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
)
EXPECTED_UPDATE_COLUMNS = {
    ("webauthn_credentials", "sign_count"),
    ("webauthn_credentials", "backed_up"),
    ("webauthn_credentials", "last_used_at"),
    ("account_action_intents", "consumed_at"),
    ("account_verification_proofs", "consumed_at"),
    ("account_recovery_codes", "consumed_at"),
    ("webauthn_enrollments", "consumed_at"),
}

_current_test = "startup"


def _check(name: str, operation) -> None:
    global _current_test
    _current_test = name
    operation()
    print(f"PASS: {name}")


def _expect_denied(conn, name: str, statement, params=()) -> None:
    def operation() -> None:
        try:
            # With the outer transaction active this becomes a savepoint.
            with conn.transaction():
                conn.execute(statement, params)
        except InsufficientPrivilege:
            return
        raise AssertionError("statement unexpectedly succeeded")

    _check(name, operation)


def _set_tenant(conn, user_id: str) -> None:
    conn.execute(
        "SELECT set_config('app.current_user_id', %s, true)",
        (user_id,),
    )


def _count_for(conn, table: str, user_id: str) -> int:
    statement = sql.SQL("SELECT count(*) FROM {} WHERE user_id = %s").format(
        sql.Identifier("public", table)
    )
    return conn.execute(statement, (user_id,)).fetchone()[0]


def _new_id() -> str:
    return uuid.uuid4().hex


def _safe_error_message(exc: Exception, secrets: tuple[str, ...] = ()) -> str:
    message = getattr(getattr(exc, "diag", None), "message_primary", None) or str(exc)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return " ".join(message.split())


def _insert_intent(conn, user_id: str, intent_id: str, now: int) -> None:
    conn.execute(
        """
        INSERT INTO account_action_intents
          (id,user_id,session_binding,session_version,action,payload_digest,
           created_at,expires_at)
        VALUES (%s,%s,%s,0,'password_add',%s,%s,%s)
        """,
        (
            intent_id,
            user_id,
            _new_id(),
            hashlib.sha256(intent_id.encode()).hexdigest(),
            now,
            now + 120,
        ),
    )


def _seed_tenant(conn, user_id: str) -> dict[str, object]:
    now = int(time.time())
    record = {
        "handle": os.urandom(32),
        "credential_id": _new_id(),
        "credential_bytes": os.urandom(32),
        "intent_id": _new_id(),
        "extra_intent_id": _new_id(),
        "proof_id": _new_id(),
        "recovery_id": _new_id(),
        "recovery_hash": os.urandom(32),
        "recovery_state_id": _new_id(),
        "enrollment_id": _new_id(),
    }

    _set_tenant(conn, user_id)
    conn.execute(
        "INSERT INTO webauthn_handles (user_id,handle) VALUES (%s,%s)",
        (user_id, record["handle"]),
    )
    conn.execute(
        """
        INSERT INTO webauthn_credentials
          (id,user_id,credential_id,public_key,algorithm,sign_count,
           backup_eligible,backed_up,created_at)
        VALUES (%s,%s,%s,%s,-7,0,true,false,%s)
        """,
        (
            record["credential_id"],
            user_id,
            record["credential_bytes"],
            b"\x01",
            now,
        ),
    )
    _insert_intent(conn, user_id, record["intent_id"], now)
    _insert_intent(conn, user_id, record["extra_intent_id"], now)
    conn.execute(
        """
        INSERT INTO account_verification_proofs
          (id,user_id,intent_id,credential_id,verified_at,expires_at)
        VALUES (%s,%s,%s,%s,%s,%s)
        """,
        (
            record["proof_id"],
            user_id,
            record["intent_id"],
            record["credential_id"],
            now,
            now + 120,
        ),
    )
    conn.execute(
        """
        INSERT INTO account_recovery_codes
          (id,user_id,code_hash,created_at)
        VALUES (%s,%s,%s,%s)
        """,
        (record["recovery_id"], user_id, record["recovery_hash"], now),
    )
    conn.execute(
        """
        INSERT INTO account_recovery_states
          (id,user_id,session_binding,session_version,status,created_at,expires_at)
        VALUES (%s,%s,%s,0,'pending',%s,%s)
        """,
        (record["recovery_state_id"], user_id, _new_id(), now, now + 120),
    )
    conn.execute(
        """
        INSERT INTO webauthn_enrollments
          (id,user_id,session_binding,session_version,method,
           signup_transaction,created_at,expires_at)
        VALUES (%s,%s,%s,0,'password',NULL,%s,%s)
        """,
        (record["enrollment_id"], user_id, _new_id(), now, now + 120),
    )
    return record


def _assert_connection_and_schema(conn) -> None:
    row = conn.execute(
        """
        SELECT current_database(), current_user,
               current_setting('server_version_num')::integer,
               r.rolsuper, r.rolbypassrls, r.rolcreatedb, r.rolcreaterole,
               EXISTS (
                 WITH RECURSIVE member_roles(roleid) AS (
                   SELECT roleid FROM pg_auth_members
                   WHERE member = (SELECT oid FROM pg_roles WHERE rolname=current_user)
                   UNION
                   SELECT am.roleid FROM pg_auth_members am
                   JOIN member_roles mr ON am.member=mr.roleid
                 )
                 SELECT 1 FROM member_roles
               )
        FROM pg_roles r
        WHERE r.rolname = current_user
        """
    ).fetchone()
    if row is None or row[:2] != (DATABASE, ROLE):
        raise AssertionError(f"unexpected database or role: {row}")
    if any(row[3:7]) or row[7]:
        raise AssertionError("app_runtime has elevated attributes or role membership")

    rows = conn.execute(
        """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
               pg_get_userbyid(c.relowner), p.policyname, p.qual, p.with_check
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
        LEFT JOIN pg_policies p
          ON p.schemaname = n.nspname AND p.tablename = c.relname
        WHERE c.relname = ANY(%s)
        ORDER BY c.relname, p.policyname
        """,
        (list(TABLES),),
    ).fetchall()
    policies: dict[str, list[tuple[str | None, str | None, str | None]]] = {}
    for table, enabled, forced, owner, policy, using_expr, check_expr in rows:
        if not enabled or not forced or owner == ROLE:
            raise AssertionError(f"RLS or owner mismatch for {table}")
        policies.setdefault(table, []).append((policy, using_expr, check_expr))
    if set(policies) != set(TABLES):
        raise AssertionError(f"missing WebAuthn tables: {set(TABLES) - set(policies)}")
    for table in TABLES:
        expected_policy = (f"{table}_tenant",)
        if len(policies[table]) != 1 or policies[table][0][0] != expected_policy[0]:
            raise AssertionError(f"unexpected tenant policies: {policies}")
        using_expr, check_expr = policies[table][0][1:]
        if (
            not using_expr
            or not check_expr
            or using_expr != check_expr
            or "user_id" not in using_expr
            or "app.current_user_id" not in using_expr
        ):
            raise AssertionError(f"unexpected tenant policy expression for {table}")


def _assert_privileges(conn) -> None:
    server_version = int(
        conn.execute(
            "SELECT current_setting('server_version_num')::integer"
        ).fetchone()[0]
    )
    privileges = TABLE_PRIVILEGES + (("MAINTAIN",) if server_version >= 170000 else ())
    expected = (True, True) + (False,) * (len(privileges) - 2)
    for table in TABLES:
        effective = tuple(
            conn.execute(
                "SELECT has_table_privilege(current_user,%s::regclass,%s)",
                (f"public.{table}", privilege),
            ).fetchone()[0]
            for privilege in privileges
        )
        if effective != expected:
            raise AssertionError(f"unexpected table privileges on {table}: {effective}")

    update_columns = {
        (table, column)
        for table, column in conn.execute(
            """
            SELECT table_name,column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ANY(%s)
              AND has_column_privilege(
                current_user,
                format('%%I.%%I', table_schema, table_name),
                column_name,
                'UPDATE'
              )
            """,
            (list(TABLES),),
        ).fetchall()
    }
    if update_columns != EXPECTED_UPDATE_COLUMNS:
        raise AssertionError(f"unexpected UPDATE columns: {update_columns}")

    user_privileges = conn.execute(
        """
        SELECT has_table_privilege(current_user,'public.users','INSERT'),
               has_table_privilege(current_user,'public.users','SELECT')
        """
    ).fetchone()
    if user_privileges != (True, True):
        raise AssertionError("app_runtime lacks required synthetic-user privileges")


def _expect_missing_context_inserts(conn, user_a: str, user_c: str) -> None:
    now = int(time.time())
    intent_id = _new_id()
    _expect_denied(
        conn,
        "missing-context handle INSERT",
        "INSERT INTO webauthn_handles (user_id,handle) VALUES (%s,%s)",
        (user_c, os.urandom(32)),
    )
    _expect_denied(
        conn,
        "missing-context intent INSERT",
        """
        INSERT INTO account_action_intents
          (id,user_id,session_binding,session_version,action,payload_digest,
           created_at,expires_at)
        VALUES (%s,%s,%s,0,'password_add',%s,%s,%s)
        """,
        (
            intent_id,
            user_a,
            _new_id(),
            hashlib.sha256(intent_id.encode()).hexdigest(),
            now,
            now + 120,
        ),
    )


def _expect_empty_context_inserts(
    conn, user_a: str, user_c: str, record_a: dict[str, object]
) -> None:
    now = int(time.time())
    proof_id = _new_id()
    intent_id = _new_id()
    session_values = (now, now + 120)
    tests = (
        (
            "webauthn_handles",
            "INSERT INTO webauthn_handles (user_id,handle) VALUES (%s,%s)",
            (user_c, os.urandom(32)),
        ),
        (
            "webauthn_credentials",
            """
            INSERT INTO webauthn_credentials
              (id,user_id,credential_id,public_key,algorithm,sign_count,
               backup_eligible,backed_up,created_at)
            VALUES (%s,%s,%s,%s,-7,0,true,false,%s)
            """,
            (_new_id(), user_a, os.urandom(32), b"\x01", now),
        ),
        (
            "account_action_intents",
            """
            INSERT INTO account_action_intents
              (id,user_id,session_binding,session_version,action,payload_digest,
               created_at,expires_at)
            VALUES (%s,%s,%s,0,'password_add',%s,%s,%s)
            """,
            (
                intent_id,
                user_c,
                _new_id(),
                hashlib.sha256(intent_id.encode()).hexdigest(),
                *session_values,
            ),
        ),
        (
            "account_verification_proofs",
            """
            INSERT INTO account_verification_proofs
              (id,user_id,intent_id,credential_id,verified_at,expires_at)
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (
                proof_id,
                user_a,
                record_a["extra_intent_id"],
                record_a["credential_id"],
                *session_values,
            ),
        ),
        (
            "account_recovery_codes",
            """
            INSERT INTO account_recovery_codes
              (id,user_id,code_hash,created_at)
            VALUES (%s,%s,%s,%s)
            """,
            (_new_id(), user_c, os.urandom(32), now),
        ),
        (
            "account_recovery_states",
            """
            INSERT INTO account_recovery_states
              (id,user_id,session_binding,session_version,status,created_at,expires_at)
            VALUES (%s,%s,%s,0,'pending',%s,%s)
            """,
            (_new_id(), user_c, _new_id(), *session_values),
        ),
        (
            "webauthn_enrollments",
            """
            INSERT INTO webauthn_enrollments
              (id,user_id,session_binding,session_version,method,
               signup_transaction,created_at,expires_at)
            VALUES (%s,%s,%s,0,'password',NULL,%s,%s)
            """,
            (_new_id(), user_c, _new_id(), *session_values),
        ),
    )
    for table, statement, params in tests:
        _expect_denied(
            conn,
            f"empty-context {table} INSERT",
            statement,
            params,
        )


def _check_tenant_reads(conn, user_a: str, user_b: str) -> None:
    expected = {
        "webauthn_handles": 1,
        "webauthn_credentials": 1,
        "account_action_intents": 2,
        "account_verification_proofs": 1,
        "account_recovery_codes": 1,
        "account_recovery_states": 1,
        "webauthn_enrollments": 1,
    }
    for table in TABLES:
        if _count_for(conn, table, user_a) != expected[table]:
            raise AssertionError(f"authorized SELECT failed for {table}")
        if _count_for(conn, table, user_b) != 0:
            raise AssertionError(f"cross-tenant SELECT exposed {table}")


def _check_cross_tenant_updates(conn, user_b: str, record_b: dict[str, object]) -> None:
    now = int(time.time())
    updates = (
        (
            "webauthn_credentials",
            "UPDATE webauthn_credentials SET sign_count=sign_count+1 WHERE id=%s AND user_id=%s",
            (record_b["credential_id"], user_b),
        ),
        (
            "account_action_intents",
            "UPDATE account_action_intents SET consumed_at=%s WHERE id=%s AND user_id=%s",
            (now, record_b["intent_id"], user_b),
        ),
        (
            "account_verification_proofs",
            "UPDATE account_verification_proofs SET consumed_at=%s WHERE id=%s AND user_id=%s",
            (now, record_b["proof_id"], user_b),
        ),
        (
            "account_recovery_codes",
            "UPDATE account_recovery_codes SET consumed_at=%s WHERE id=%s AND user_id=%s",
            (now, record_b["recovery_id"], user_b),
        ),
        (
            "webauthn_enrollments",
            "UPDATE webauthn_enrollments SET consumed_at=%s WHERE id=%s AND user_id=%s",
            (now, record_b["enrollment_id"], user_b),
        ),
    )
    for table, statement, params in updates:
        if conn.execute(statement, params).rowcount != 0:
            raise AssertionError(f"cross-tenant UPDATE affected {table}")


def _check_authorized_updates(conn, user_a: str, record_a: dict[str, object]) -> None:
    now = int(time.time())
    updates = (
        (
            "webauthn_credentials",
            "UPDATE webauthn_credentials SET sign_count=1,backed_up=true,last_used_at=%s WHERE id=%s AND user_id=%s",
            (now + 1, record_a["credential_id"], user_a),
        ),
        (
            "account_action_intents",
            "UPDATE account_action_intents SET consumed_at=%s WHERE id=%s AND user_id=%s",
            (now, record_a["intent_id"], user_a),
        ),
        (
            "account_verification_proofs",
            "UPDATE account_verification_proofs SET consumed_at=%s WHERE id=%s AND user_id=%s",
            (now, record_a["proof_id"], user_a),
        ),
        (
            "account_recovery_codes",
            "UPDATE account_recovery_codes SET consumed_at=%s WHERE id=%s AND user_id=%s",
            (now, record_a["recovery_id"], user_a),
        ),
        (
            "webauthn_enrollments",
            "UPDATE webauthn_enrollments SET consumed_at=%s WHERE id=%s AND user_id=%s",
            (now, record_a["enrollment_id"], user_a),
        ),
    )
    for table, statement, params in updates:
        if conn.execute(statement, params).rowcount != 1:
            raise AssertionError(f"authorized UPDATE failed for {table}")


def _verify_rollback(conn, user_ids: list[str]) -> None:
    conn.execute("SET TRANSACTION READ ONLY")
    for user_id in user_ids:
        if conn.execute(
            "SELECT count(*) FROM users WHERE id=%s", (user_id,)
        ).fetchone()[0]:
            raise AssertionError("synthetic user persisted after rollback")
        _set_tenant(conn, user_id)
        for table in TABLES:
            if _count_for(conn, table, user_id):
                raise AssertionError(f"synthetic {table} row persisted after rollback")
    conn.rollback()


def main() -> int:
    password = getpass("Password for app_runtime on the local test DB: ")
    try:
        conn = psycopg.connect(
            host=HOST,
            port=PORT,
            dbname=DATABASE,
            user=ROLE,
            password=password,
            connect_timeout=5,
            application_name="vervfy_webauthn_rls_local_test",
        )
    except psycopg.Error as exc:
        print(
            "NOT TESTED: local app_runtime authentication "
            f"({type(exc).__name__}: {_safe_error_message(exc, (password,))}; "
            f"SQLSTATE={getattr(exc, 'sqlstate', None)})"
        )
        return 2
    finally:
        password = ""

    user_ids: list[str] = []
    try:
        conn.execute("SET LOCAL search_path TO public")
        _check(
            "database, role, and RLS preflight",
            lambda: _assert_connection_and_schema(conn),
        )
        _check(
            "effective privileges for all seven tables",
            lambda: _assert_privileges(conn),
        )

        user_ids = [_new_id(), _new_id(), _new_id()]
        now = time.time()
        for user_id in user_ids:
            conn.execute(
                """
                INSERT INTO users (id,username,username_key,email,created_at)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    user_id,
                    "e2e_" + user_id[:24],
                    "e2e_" + user_id[:24],
                    f"e2e+{user_id}@example.test",
                    now,
                ),
            )
        user_a, user_b, user_c = user_ids

        def missing_context_preflight() -> None:
            if (
                conn.execute(
                    "SELECT current_setting('app.current_user_id',true)"
                ).fetchone()[0]
                is not None
            ):
                raise AssertionError("tenant context was set on a fresh connection")

        _check("fresh connection has no tenant context", missing_context_preflight)
        _expect_missing_context_inserts(conn, user_a, user_c)

        records = {
            user_a: _seed_tenant(conn, user_a),
            user_b: _seed_tenant(conn, user_b),
        }

        _set_tenant(conn, "")

        def empty_context_reads() -> None:
            for table in TABLES:
                if _count_for(conn, table, user_a) or _count_for(conn, table, user_b):
                    raise AssertionError(f"{table} visible without valid context")

        _check(
            "empty tenant context hides rows in all seven tables", empty_context_reads
        )
        _expect_empty_context_inserts(conn, user_a, user_c, records[user_a])

        _set_tenant(conn, user_a)
        _check(
            "authorized and cross-tenant SELECT across all seven tables",
            lambda: _check_tenant_reads(conn, user_a, user_b),
        )
        _check(
            "cross-tenant UPDATE filtered on every updateable table",
            lambda: _check_cross_tenant_updates(conn, user_b, records[user_b]),
        )
        _check(
            "authorized column UPDATEs",
            lambda: _check_authorized_updates(conn, user_a, records[user_a]),
        )

        record_a = records[user_a]
        forbidden_updates = (
            (
                "webauthn_handles",
                "UPDATE webauthn_handles SET handle=handle WHERE user_id=%s",
                (user_a,),
            ),
            (
                "webauthn_credentials",
                "UPDATE webauthn_credentials SET algorithm=algorithm WHERE id=%s AND user_id=%s",
                (record_a["credential_id"], user_a),
            ),
            (
                "account_action_intents",
                "UPDATE account_action_intents SET action=action WHERE id=%s AND user_id=%s",
                (record_a["intent_id"], user_a),
            ),
            (
                "account_verification_proofs",
                "UPDATE account_verification_proofs SET credential_id=credential_id WHERE id=%s AND user_id=%s",
                (record_a["proof_id"], user_a),
            ),
            (
                "account_recovery_codes",
                "UPDATE account_recovery_codes SET code_hash=code_hash WHERE id=%s AND user_id=%s",
                (record_a["recovery_id"], user_a),
            ),
            (
                "account_recovery_states",
                "UPDATE account_recovery_states SET status=status WHERE id=%s AND user_id=%s",
                (record_a["recovery_state_id"], user_a),
            ),
            (
                "webauthn_enrollments",
                "UPDATE webauthn_enrollments SET method=method WHERE id=%s AND user_id=%s",
                (record_a["enrollment_id"], user_a),
            ),
        )
        for table, statement, params in forbidden_updates:
            _expect_denied(
                conn, f"ungranted UPDATE denied on {table}", statement, params
            )

        for table in TABLES:
            statement = sql.SQL("DELETE FROM {} WHERE user_id=%s").format(
                sql.Identifier("public", table)
            )
            _expect_denied(conn, f"DELETE denied on {table}", statement, (user_a,))

        for table in TABLES:
            _expect_denied(
                conn,
                f"RLS disable denied on {table}",
                sql.SQL("ALTER TABLE {} DISABLE ROW LEVEL SECURITY").format(
                    sql.Identifier("public", table)
                ),
            )
            _expect_denied(
                conn,
                f"policy change denied on {table}",
                sql.SQL("ALTER POLICY {} ON {} USING (true)").format(
                    sql.Identifier(f"{table}_tenant"),
                    sql.Identifier("public", table),
                ),
            )

        _set_tenant(conn, user_b)

        def report_mutable_context() -> None:
            for table in TABLES:
                expected = 2 if table == "account_action_intents" else 1
                if _count_for(conn, table, user_b) != expected:
                    raise AssertionError(f"selected GUC context failed for {table}")

        _check(
            "app_runtime can select its GUC context (trust-model limitation)",
            report_mutable_context,
        )

        # No commit path exists. This rollback runs even if any assertion fails.
        conn.rollback()
        _check(
            "synthetic data absent after rollback",
            lambda: _verify_rollback(conn, user_ids),
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - report failures after guaranteed rollback
        print(
            f"FAIL: {_current_test} "
            f"({type(exc).__name__}: {_safe_error_message(exc)}; "
            f"SQLSTATE={getattr(exc, 'sqlstate', None)})"
        )
        conn.rollback()
        if user_ids:
            try:
                _verify_rollback(conn, user_ids)
                print("PASS: synthetic data absent after failure rollback")
            except Exception as rollback_exc:  # noqa: BLE001 - report rollback verification failure
                print(
                    "FAIL: rollback verification "
                    f"({type(rollback_exc).__name__}: "
                    f"{_safe_error_message(rollback_exc)}; "
                    f"SQLSTATE={getattr(rollback_exc, 'sqlstate', None)})"
                )
        return 1
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
