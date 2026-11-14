"""Static preparation checks only. Never imports the runner or executes SQL."""
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
allowed_calls = {
 'current_setting','pg_backend_pid','to_regclass','to_regnamespace','to_regprocedure',
 'string_to_array','has_database_privilege','has_schema_privilege','has_table_privilege',
 'has_column_privilege','has_any_column_privilege','has_sequence_privilege',
 'has_function_privilege','pg_has_role','md5','pg_get_expr','pg_get_constraintdef',
 'aclexplode','acldefault',
}
reports = []
for name in ('01-catalogs.sql', '02-storage-metadata.sql'):
    raw = (ROOT / name).read_text()
    code = re.sub(r'--[^\n]*', '', raw)
    code = re.sub(r"'(?:''|[^'])*'", "''", code)
    for command in re.findall(r'\\([a-zA-Z_!]+)', code):
        assert command in {'set','pset','if','else','endif','echo','quit','gset'}, command
    code = re.sub(r'\\gset\b', ';', code)
    code = re.sub(r'^\s*\\[^\n]*', '', code, flags=re.M)
    # A lexical defense and review aid, not a PostgreSQL grammar/safety proof.
    banned = re.findall(r'\b(INSERT|UPDATE|DELETE|MERGE|COPY|CREATE|ALTER|DROP|GRANT|REVOKE|TRUNCATE|CALL|DO|EXECUTE|INTO|VACUUM|ANALYZE|REFRESH|LOCK|LISTEN|NOTIFY|COMMIT|RESET)\b', code, flags=re.I)
    assert not banned, (name, banned)
    calls = set(re.findall(r'pg_catalog\.([a-z_]+)\s*\(', code))
    assert calls <= allowed_calls, (name, calls - allowed_calls)
    statements = [s.strip() for s in code.split(';') if s.strip()]
    for statement in statements:
        assert re.match(r'^(SELECT\b|WITH\b|BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY\b|ROLLBACK\b|SET LOCAL (search_path|statement_timeout|lock_timeout)\s*=)', statement, re.I), statement[:80]
    assert sum(s.upper().startswith('BEGIN ') for s in statements) == 1
    assert sum(s.upper() == 'ROLLBACK' for s in statements) == 1
    assert not re.search(r'\bFROM\s+(?:ONLY\s+)?(?:public\.(?!alembic_version\b)|storage\.(?!buckets\b)|vervfy_storage\.(?!namespaces\b))', code, re.I)
    assert not re.search(r'pg_catalog\.(pg_authid|pg_stat_activity|pg_user_mappings|pg_subscription)\b', code, re.I)
    reports.append({'file': name, 'sha256': hashlib.sha256(raw.encode()).hexdigest(),
                    'static_keyword_and_meta_command_review': 'PASS',
                    'built_in_catalog_calls': sorted(calls)})
for path in ROOT.glob('*.py'):
    ast.parse(path.read_text(), filename=str(path))
print(json.dumps({'verification': 'STATIC_ONLY', 'sql_executed': False,
                  'hosted_connections': False, 'runtime_sql_syntax_and_permissions': 'NOT_EXECUTED',
                  'python_syntax': 'PASS', 'queries': reports}, indent=2))
