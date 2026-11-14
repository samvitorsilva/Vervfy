"""Exercise the actual preflight predicate in disposable, socket-only PostgreSQL.

No application imports, hosted environment, migration runner, or existing cluster.
"""
from pathlib import Path
import json
from collections import defaultdict
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / 'docs/staging-alembic-preflight.sql').read_text()
PREDICATE = SQL.split('-- BEGIN APPLICATION EMPTY PREDICATE', 1)[1]
PREDICATE = PREDICATE.split('\n IF ', 1)[1].split('-- END APPLICATION EMPTY PREDICATE', 1)[0]


class ApplicationEmptinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binaries = {name: shutil.which(name) for name in ('initdb', 'pg_ctl', 'psql')}
        if not all(cls.binaries.values()):
            raise unittest.SkipTest('local PostgreSQL binaries required')
        cls.temp = tempfile.TemporaryDirectory(prefix='vervfy-empty-test-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.path = Path(cls.temp.name)
        cls.env = {'PATH': '/usr/bin:/bin', 'HOME': cls.temp.name, 'LANG': 'C.UTF-8'}
        cls.run_local([cls.binaries['initdb'], '-D', str(cls.path / 'data'),
                       '-U', 'postgres', '--auth=trust', '--no-locale'])
        cls.run_local([cls.binaries['pg_ctl'], '-D', str(cls.path / 'data'),
                       '-l', str(cls.path / 'server.log'), '-o',
                       f"-h '' -k {cls.path} -p 55439", '-w', 'start'])
        cls.addClassCleanup(cls.run_local, [cls.binaries['pg_ctl'], '-D',
                            str(cls.path / 'data'), '-m', 'immediate', '-w', 'stop'])

    @classmethod
    def run_local(cls, command, **kwargs):
        return subprocess.run(command, env=cls.env, check=True,
                              capture_output=True, timeout=30, **kwargs)

    def blocked(self, setup):
        script = ('BEGIN; CREATE ROLE vervfy_oauth_staging_user; '
                  + setup + '\nSELECT (' + PREDICATE + ')::text;\nROLLBACK;')
        result = self.run_local([self.binaries['psql'], '-X', '-qAt',
            '-h', str(self.path), '-p', '55439', '-U', 'postgres', '-d', 'postgres',
            '-v', 'ON_ERROR_STOP=1', '-f', '-'], input=script.encode())
        self.assertIn(result.stdout.strip(), (b'true', b'false'))
        return result.stdout.strip() == b'true'

    def test_empty_and_provider_schemas(self):
        self.assertFalse(self.blocked(''))
        self.assertFalse(self.blocked(' '.join(
            f'CREATE SCHEMA {name}; CREATE TABLE {name}.managed(id int);'
            for name in ('auth', 'storage', 'realtime', 'vault'))))

    def test_application_objects(self):
        cases = {
            'private_schema': 'CREATE SCHEMA vervfy_auth;',
            'table': 'CREATE TABLE public.users(id int);',
            'history': 'CREATE TABLE public.alembic_version(version_num text);',
            'sequence': 'CREATE SEQUENCE public.orphan;',
            'view': 'CREATE VIEW public.orphan AS SELECT 1 AS id;',
            'materialized_view': 'CREATE MATERIALIZED VIEW public.orphan AS SELECT 1 AS id;',
            'partitioned_table': 'CREATE TABLE public.orphan(id int) PARTITION BY RANGE(id);',
            'function': "CREATE FUNCTION public.orphan() RETURNS int LANGUAGE sql AS 'SELECT 1';",
            'procedure': "CREATE PROCEDURE public.orphan() LANGUAGE sql AS 'SELECT 1';",
            'enum': "CREATE TYPE public.orphan AS ENUM ('x');",
            'composite': 'CREATE TYPE public.orphan AS (id int);',
            'domain': 'CREATE DOMAIN public.orphan AS int;',
            'collation': 'CREATE COLLATION public.orphan FROM "C";',
            'text_search': 'CREATE TEXT SEARCH CONFIGURATION public.orphan (COPY=pg_catalog.simple);',
        }
        for name, setup in cases.items():
            with self.subTest(name=name):
                self.assertTrue(self.blocked(setup))

    def test_cross_schema_ownership_and_default_acl(self):
        for setup in (
            'CREATE SCHEMA auth; CREATE TABLE auth.stray(id int); ALTER TABLE auth.stray OWNER TO vervfy_oauth_staging_user;',
            'CREATE SCHEMA stray AUTHORIZATION vervfy_oauth_staging_user;',
            "CREATE SCHEMA auth; CREATE FUNCTION auth.stray() RETURNS int LANGUAGE sql AS 'SELECT 1'; ALTER FUNCTION auth.stray() OWNER TO vervfy_oauth_staging_user;",
        ):
            with self.subTest(setup=setup):
                self.assertTrue(self.blocked(setup))
        self.assertFalse(self.blocked('ALTER DEFAULT PRIVILEGES FOR ROLE vervfy_oauth_staging_user REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;'))

    def baseline_setup(self):
        rows = json.loads((ROOT / 'tests/fixtures/staging_default_acl_baseline.json').read_text())
        self.assertEqual(len(rows), 96)
        groups = defaultdict(list)
        for row in rows:
            self.assertEqual(row['schema'], 'public')
            self.assertEqual(row['grantor'], row['owner'])
            self.assertIs(row['grant_option'], False)
            groups[(row['owner'], row['object_category'], row['grantee'])].append(row['privilege'])
        statements = ['CREATE ROLE supabase_admin;', 'CREATE ROLE anon;',
                      'CREATE ROLE authenticated;', 'CREATE ROLE service_role;']
        for (owner, category, grantee), privileges in groups.items():
            statements.append(f'ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public '
                              f'GRANT {", ".join(privileges)} ON {category} TO {grantee};')
        statements.append("""DO $$ BEGIN
          IF (SELECT count(*) FROM pg_default_acl WHERE defaclnamespace='public'::regnamespace) <> 6
          OR (SELECT count(*) FROM pg_default_acl d CROSS JOIN LATERAL aclexplode(d.defaclacl) a
              WHERE d.defaclnamespace='public'::regnamespace) <> 96
          THEN RAISE EXCEPTION 'Incorrect synthetic baseline'; END IF;
        END $$;""")
        return ' '.join(statements)

    def test_exact_six_acl_baseline(self):
        self.assertFalse(self.blocked(self.baseline_setup()))

    def test_defaults_follow_creator_not_schema(self):
        script = ('BEGIN; CREATE ROLE vervfy_oauth_staging_user; ' + self.baseline_setup() + """
          GRANT USAGE, CREATE ON SCHEMA public TO vervfy_oauth_staging_user;
          ALTER DEFAULT PRIVILEGES FOR ROLE vervfy_oauth_staging_user
            REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
          SET ROLE vervfy_oauth_staging_user;
          CREATE TABLE public.migration_probe(id int);
          CREATE FUNCTION public.migration_probe_fn() RETURNS int LANGUAGE sql AS 'SELECT 1';
          RESET ROLE;
          CREATE TABLE public.provider_probe(id int);
          CREATE FUNCTION public.provider_probe_fn() RETURNS int LANGUAGE sql AS 'SELECT 1';
          SELECT has_table_privilege('anon','public.migration_probe','SELECT'),
                 has_table_privilege('authenticated','public.migration_probe','SELECT'),
                 has_function_privilege('anon','public.migration_probe_fn()','EXECUTE'),
                 has_function_privilege('authenticated','public.migration_probe_fn()','EXECUTE'),
                 has_table_privilege('anon','public.provider_probe','SELECT'),
                 has_function_privilege('authenticated','public.provider_probe_fn()','EXECUTE');
          ROLLBACK;
        """)
        result = self.run_local([self.binaries['psql'], '-X', '-qAt',
            '-h', str(self.path), '-p', '55439', '-U', 'postgres', '-d', 'postgres',
            '-v', 'ON_ERROR_STOP=1', '-f', '-'], input=script.encode())
        self.assertEqual(result.stdout.strip(), b'f|f|f|f|t|t')

    def test_baseline_does_not_hide_unexpected_acl_or_application_state(self):
        mutations = {
            'extra_grantee': 'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT ON TABLES TO PUBLIC;',
            'missing_privilege': 'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE MAINTAIN ON TABLES FROM anon;',
            'grant_option': 'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT SELECT ON TABLES TO anon WITH GRANT OPTION;',
            'vervfy_owner': 'ALTER DEFAULT PRIVILEGES FOR ROLE vervfy_oauth_staging_user IN SCHEMA public GRANT SELECT ON TABLES TO anon;',
            'unexpected_category': 'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT USAGE ON TYPES TO anon;',
            'wrong_grantor': "UPDATE pg_default_acl SET defaclacl=replace(defaclacl::text,'/postgres','/supabase_admin')::aclitem[] WHERE defaclrole='postgres'::regrole AND defaclnamespace='public'::regnamespace;",
            'global_vervfy_grant': 'ALTER DEFAULT PRIVILEGES FOR ROLE vervfy_oauth_staging_user GRANT SELECT ON TABLES TO anon;',
            'unsafe_function_default': 'ALTER DEFAULT PRIVILEGES FOR ROLE vervfy_oauth_staging_user REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC; ALTER DEFAULT PRIVILEGES FOR ROLE vervfy_oauth_staging_user GRANT EXECUTE ON FUNCTIONS TO anon;',
            'history': 'CREATE TABLE public.alembic_version(version_num text);',
            'private_schema': 'CREATE SCHEMA vervfy_auth;',
            'routine': "CREATE FUNCTION public.stray() RETURNS int LANGUAGE sql AS 'SELECT 1';",
            'type': "CREATE TYPE public.stray AS ENUM ('x');",
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                self.assertTrue(self.blocked(self.baseline_setup() + mutation))

    def test_extension_membership_is_not_a_name_or_owner_exemption(self):
        function = "CREATE FUNCTION public.fixture() RETURNS int LANGUAGE sql AS 'SELECT 1';"
        # A synthetic member of the built-in, provider-owned pg_catalog extension.
        member = function + 'ALTER EXTENSION plpgsql ADD FUNCTION public.fixture();'
        self.assertFalse(self.blocked(member))
        self.assertFalse(self.blocked("CREATE TYPE public.fixture AS ENUM ('x'); ALTER EXTENSION plpgsql ADD TYPE public.fixture;"))
        self.assertTrue(self.blocked(function))
        self.assertTrue(self.blocked(member + 'ALTER FUNCTION public.fixture() OWNER TO vervfy_oauth_staging_user;'))
        self.assertTrue(self.blocked('CREATE TABLE public.fixture(id int); ALTER EXTENSION plpgsql ADD TABLE public.fixture;'))
        self.assertTrue(self.blocked('CREATE EXTENSION hstore SCHEMA public;'))


if __name__ == '__main__':
    unittest.main()
