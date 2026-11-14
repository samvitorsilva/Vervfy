"""Static checks only. No database libraries, subprocesses or connections."""
from pathlib import Path
import hashlib
import json
import re

root=Path(__file__).resolve().parent
path=root/'production-catalog.sql'
raw=path.read_text()
code=re.sub(r'--[^\n]*','',raw)
code=re.sub(r"'(?:''|[^'])*'","''",code)
assert not re.search(r'\b(CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|MERGE|GRANT|REVOKE|COPY|TRUNCATE|CALL|EXECUTE|COMMIT|VACUUM|ANALYZE|REFRESH|INTO)\b',code,re.I)
assert raw.count('BEGIN READ ONLY;')==1
assert code.rstrip().endswith('ROLLBACK;')
assert '\\' not in raw and ":'" not in raw
assert "statement_timeout = '30s'" in raw and "lock_timeout = '3s'" in raw
assert 'pg_catalog.pg_authid' not in raw and 'pg_stat_activity' not in raw
assert 'p.prosrc' not in raw and 'pg_get_functiondef' not in raw
calls=set(re.findall(r'pg_catalog\.([a-z_]+)\s*\(',code))
allowed={'current_setting','to_regnamespace','to_regprocedure','pg_get_userbyid',
 'has_database_privilege','has_schema_privilege','has_table_privilege',
 'has_column_privilege','has_any_column_privilege','has_sequence_privilege',
 'has_function_privilege','pg_has_role','md5','pg_get_expr','pg_get_constraintdef',
 'aclexplode','acldefault'}
assert calls<=allowed,calls-allowed
references=set(re.findall(r'\b(?:FROM|JOIN)\s+(?:ONLY\s+)?([a-z_]+\.[a-z_]+)',code,re.I))
assert all(x.startswith('pg_catalog.') or x=='public.alembic_version' for x in references),references
assert raw.count('FROM ONLY public.alembic_version')==1
result={'status':'STATIC_CHECKS_PASS','sql_executed':False,'hosted_access':False,
 'postgresql_parser_or_runtime_validation':'NOT_PERFORMED: user prohibits SQL execution; no PostgreSQL grammar parser used',
 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
 'catalog_function_allowlist':sorted(calls),'qualified_relation_reads':sorted(references)}
print(json.dumps(result,indent=2))
