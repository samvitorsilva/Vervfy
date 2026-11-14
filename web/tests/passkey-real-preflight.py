"""Read-only isolation gate. Never import server/db (which initialize services).

Requires psutil, psycopg, redis and sqlalchemy in the selected Python environment.
No migrations, writes, cleanup, or implicit fallback targets are permitted.
"""
import ipaddress
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path

import psutil
import psycopg
import redis
from sqlalchemy.engine import make_url


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def environment(pid):
    return dict(item.split('=', 1) for item in Path(f'/proc/{pid}/environ').read_text().split('\0') if '=' in item)


def parse_ss_owner(output, port):
    lines = output.strip().splitlines()
    require(len(lines) == 1, f'Privileged inspection requires exactly one listener on {port}')
    fields = lines[0].split(maxsplit=5)
    require(len(fields) == 6 and fields[0] == 'LISTEN'
            and fields[3] == f'127.0.0.1:{port}' and fields[4] == '0.0.0.0:*',
            f'Privileged listener binding is unexpected on {port}')
    # Parse the entire ownership field, rejecting partial or ambiguous output.
    owner = re.fullmatch(r'users:\(\("caddy",pid=([1-9][0-9]*),fd=[0-9]+\)\)', fields[5])
    require(owner is not None, f'Privileged inspection did not identify one Caddy owner on {port}')
    return int(owner.group(1))


def privileged_caddy_owner(port):
    require(port in (443, 2019), 'Privileged inspection is restricted to Caddy ports')
    try:
        result = subprocess.run(
            ['/usr/bin/sudo', '-n', '--', '/usr/bin/ss', '-H', '-ltnp',
             f'sport = :{port}'],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=10, check=False,
            env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f'Privileged Caddy socket inspection unavailable on {port}') from exc
    require(result.returncode == 0 and not result.stderr.strip(),
            f'Privileged Caddy socket inspection unavailable on {port}; '
            'noninteractive sudo permission for the exact ss command is required')
    return parse_ss_owner(result.stdout, port)


def listener(port):
    """Require one IPv4 loopback socket and independently confirm its owner.

    Linux psutil may expose a socket with pid=None when /proc/<pid>/fd
    is inaccessible. That is unknown ownership, not an absent listener.
    Never substitute a service MainPID or a previously observed PID.
    """
    try:
        found = [c for c in psutil.net_connections(kind='tcp')
                 if c.status == psutil.CONN_LISTEN and c.laddr.port == port]
    except (psutil.AccessDenied, PermissionError) as exc:
        raise RuntimeError(f'Cannot inspect TCP listeners on {port}: permission denied') from exc
    require(found, f'No TCP listener visible on {port}; verify the host network namespace and inspection permissions')
    require(len(found) == 1, f'Expected one TCP listener on {port}, found {len(found)}')
    connection = found[0]
    require(connection.family == socket.AF_INET and connection.laddr.ip == '127.0.0.1',
            f'Listener on {port} is not exclusively IPv4 loopback (127.0.0.1)')
    owner_pid = connection.pid
    privileged = owner_pid is None and port in (443, 2019)
    if privileged:
        owner_pid = privileged_caddy_owner(port)
    require(owner_pid is not None, f'Listener owner unavailable on {port}: insufficient inspection permissions')
    try:
        process = psutil.Process(owner_pid)
        if privileged:
            require(process.name() == 'caddy', 'Privileged socket owner is not Caddy')
            require(privileged_caddy_owner(port) == process.pid and process.is_running(),
                    f'Caddy listener ownership changed on {port}')
            return process
        owned = [c for c in process.net_connections(kind='tcp')
                 if c.status == psutil.CONN_LISTEN and c.laddr.port == port]
        require(len(owned) == 1 and owned[0].family == socket.AF_INET
                and owned[0].laddr.ip == '127.0.0.1',
                f'Listener ownership changed or could not be corroborated on {port}')
        require(process.is_running(), f'Listener owner exited on {port}')
        return process
    except (psutil.AccessDenied, PermissionError) as exc:
        raise RuntimeError(f'Cannot corroborate listener owner on {port}: permission denied') from exc
    except psutil.NoSuchProcess as exc:
        raise RuntimeError(f'Listener owner exited while inspecting port {port}') from exc


def validate_database_url(value):
    try:
        db = make_url(value)
        valid = (db.drivername in ('postgres', 'postgresql', 'postgresql+psycopg')
                 and db.host == '127.0.0.1' and db.port == 5433
                 and db.database == 'vervfy_passkey_e2e' and not db.query)
    except Exception:  # noqa: BLE001 -- redact URL parser errors
        raise RuntimeError('Invalid isolated database inspection target') from None
    require(valid, 'Database target must be exactly 127.0.0.1:5433/vervfy_passkey_e2e without overrides')
    return db


def backend_connections(backend):
    # Reject subprocesses rather than silently omit a worker's database sockets.
    require(not backend.children(recursive=True), 'Backend subprocesses require explicit connection auditing')
    require(not backend.net_connections(kind='unix'), 'Backend Unix sockets prevent exhaustive TCP database verification')
    connections = backend.net_connections(kind='tcp')
    outbound = [c for c in connections if c.raddr and c.laddr.port != 8000]
    for c in outbound:
        require(c.status == psutil.CONN_ESTABLISHED and c.family == socket.AF_INET
                and c.laddr.ip == '127.0.0.1' and c.raddr.ip == '127.0.0.1'
                and c.raddr.port in (5433, 6380),
                'Unexpected or transitional backend outbound connection')
    return {c.laddr.port for c in outbound if c.raddr.port == 5433}, {
        c.laddr.port for c in outbound if c.raddr.port == 6380}


def postgres_container():
    # Fixed local daemon and object; never honor DOCKER_HOST or remote contexts.
    try:
        result = subprocess.run(
            ['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock', 'inspect',
             '--format', '{{json .}}', 'vervfy-oauth-local-postgres-1'],
            capture_output=True, text=True, timeout=10, check=False,
        )
        require(result.returncode == 0, 'Local PostgreSQL container metadata inspection unavailable')
        metadata = json.loads(result.stdout)
        require(metadata['State']['Running'], 'PostgreSQL container is not running')
        network = metadata['NetworkSettings']
        require(network['Ports'].get('5432/tcp') == [
            {'HostIp': '127.0.0.1', 'HostPort': '5433'}],
            'PostgreSQL published endpoint is not exclusively 127.0.0.1:5433 -> 5432')
        addresses = {n['IPAddress'] for n in network['Networks'].values() if n['IPAddress']}
        require(len(addresses) == 1, 'Ambiguous PostgreSQL container network address')
        address = addresses.pop()
        parsed = ipaddress.ip_address(address)
        require(parsed.version == 4 and parsed.is_private and not parsed.is_loopback,
                'Unexpected PostgreSQL bridge address')
        return metadata['Id'], address
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError) as exc:
        raise RuntimeError('Cannot verify local PostgreSQL container metadata') from exc


def parse_nat_mapping(output, ports, server_address):
    """Map original host sockets to server-visible peers from kernel tuples.

    The reverse reply tuple exposes both SNAT address and translated source port.
    Never infer port preservation or correlate by counts/application_name.
    """
    mapping = {}
    for port in ports:
        matches = []
        for line in output.splitlines():
            tuples = re.findall(r'src=(\S+) dst=(\S+) sport=(\d+) dport=(\d+)', line)
            if not tuples or tuples[0] != ('127.0.0.1', '127.0.0.1', str(port), '5433'):
                continue
            require('tcp' in line.split() and 'ESTABLISHED' in line.split()
                    and len(tuples) == 2, 'Unusable PostgreSQL conntrack entry')
            reply_source, peer, reply_port, peer_port = tuples[1]
            require(reply_source == server_address and reply_port == '5432',
                    'PostgreSQL flow does not terminate at the verified container')
            require(ipaddress.ip_address(peer).version == 4 and 0 < int(peer_port) < 65536,
                    'Invalid server-visible PostgreSQL peer')
            matches.append((peer, int(peer_port)))
        require(len(matches) == 1,
                'Missing or ambiguous kernel NAT mapping for a FastAPI PostgreSQL socket; '
                'userland proxy connections require separate evidence')
        mapping[port] = matches[0]
    require(len(set(mapping.values())) == len(mapping), 'Multiple host sockets map to one PostgreSQL peer')
    return mapping


def postgres_nat_mapping(ports, address):
    # Reading kernel state cannot change firewall rules or connections.
    for filename in ('/proc/net/nf_conntrack', '/proc/net/ip_conntrack'):
        try:
            return parse_nat_mapping(Path(filename).read_text(), ports, address)
        except (FileNotFoundError, PermissionError):
            continue
    raise RuntimeError('Live kernel conntrack evidence unavailable; PostgreSQL NAT correlation cannot be established')


def verify_pg_connections(conn, mapping):
    require(mapping, 'No live FastAPI PostgreSQL connection: effective target cannot be proved')
    for address, port in mapping.values():
        rows = conn.execute(
            'SELECT datname FROM pg_stat_activity WHERE client_addr = %s AND client_port = %s',
            (address, port),
        ).fetchall()
        require(rows == [('vervfy_passkey_e2e',)],
                'Translated FastAPI socket does not uniquely correlate to the isolated database; '
                'check statistics visibility and live NAT evidence')


def main():
    require(os.geteuid() != 0, 'Run this preflight unprivileged; only the fixed ss inspection may use sudo')
    require({x[4][0] for x in socket.getaddrinfo('vervfy.test', 443)} == {'127.0.0.1'}, 'Origin must resolve exclusively to loopback')
    backend, frontend, caddy = listener(8000), listener(3000), listener(443)
    require('server:app' in ' '.join(backend.cmdline()), 'FastAPI listener is not identifiable as server:app')
    require(caddy.name() == 'caddy', 'HTTPS listener is not Caddy')
    env = environment(backend.pid)
    require(env.get('VERVFY_ENVIRONMENT', '').lower() != 'production', 'Production mode forbidden')
    # /proc exposes the launch environment, not Python's subsequent os.environ
    # assignments. If present, reject conflicting launch configuration, but never
    # use it as proof of the effective database or as inspection credentials.
    if env.get('DATABASE_URL'):
        validate_database_url(env['DATABASE_URL'])
    inspection_value = os.environ.get('VERVFY_PREFLIGHT_DATABASE_URL')
    require(inspection_value, 'VERVFY_PREFLIGHT_DATABASE_URL is required: supply an independent local inspection credential')
    db = validate_database_url(inspection_value)
    require(db.username and db.password, 'Explicit inspection username and password are required')
    require(not any(k.startswith('PG') for k in os.environ),
            'Remove PG* environment overrides before database inspection')
    from urllib.parse import urlsplit
    rv = urlsplit(env.get('REDIS_URL', ''))
    require(rv.scheme == 'redis' and rv.hostname == '127.0.0.1' and rv.port == 6380 and rv.path == '/1' and not rv.query and not rv.fragment, 'Valkey must use isolated DB 1')
    require(env.get('VERVFY_WEBAUTHN_ENABLED') == '1' and env.get('VERVFY_WEBAUTHN_RP_ID') == 'vervfy.test' and json.loads(env.get('VERVFY_WEBAUTHN_ORIGINS', 'null')) == ['https://vervfy.test'] and env.get('VERVFY_WEBAUTHN_RP_NAME'), 'WebAuthn configuration not verified')
    require(env.get('GOOGLE_OAUTH_ENABLED', '0').lower() in ('0', 'false'), 'Google OAuth must be disabled')
    require(environment(frontend.pid).get('BACKEND_URL') == 'http://127.0.0.1:8000', 'Next.js upstream cannot be verified')
    # Inspect active Caddy configuration, never merely a potentially stale file.
    admin = listener(2019)
    require(admin.pid == caddy.pid, 'Caddy admin listener ownership mismatch')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise RuntimeError('Caddy admin redirect forbidden')

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open('http://127.0.0.1:2019/config/', timeout=5) as response:
        config = json.load(response)
    servers = config['apps']['http']['servers']
    require(len(servers) == 1, 'Unsupported Caddy server layout; inspect before adapting gate')
    server = next(iter(servers.values()))
    require(server['listen'] == ['127.0.0.1:443'], 'Unexpected Caddy listeners')
    routes = server['routes']
    require(len(routes) == 1 and routes[0].get('match') == [{'host': ['vervfy.test']}], 'Unexpected Caddy host routing')
    upstreams = []
    def inspect(value):
        if isinstance(value, dict):
            if 'handler' in value:
                require(value['handler'] in ('subroute', 'reverse_proxy'), 'Unsupported Caddy handler')
            if value.get('handler') == 'reverse_proxy':
                require(not any(k in value for k in ('dynamic_upstreams', 'transport', 'rewrite')), 'Unsupported Caddy proxy overrides')
                upstreams.extend(x['dial'] for x in value['upstreams'])
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
    inspect(routes)
    require(upstreams and set(upstreams) <= {'127.0.0.1:3000', '127.0.0.1:8000'}, 'Caddy upstream outside isolated services')
    # Verify system CA trust and hostname without HTTP requests or TLS bypasses.
    # Chromium uses its own trust integration; this is not a Chromium trust claim.
    with (
        socket.create_connection(('127.0.0.1', 443), timeout=5) as tcp,
        ssl.create_default_context().wrap_socket(tcp, server_hostname='vervfy.test'),
    ):
        pass
    # Tie live application TCP connections to server-side DB/Valkey observations.
    pg_ports, redis_ports = backend_connections(backend)
    require(pg_ports and redis_ports, 'No live backend DB/Valkey connections to independently verify')
    container_identity = postgres_container()
    nat_mapping = postgres_nat_mapping(pg_ports, container_identity[1])
    with psycopg.connect(host='127.0.0.1', hostaddr='127.0.0.1', port=5433, dbname='vervfy_passkey_e2e', user=db.username, password=db.password, connect_timeout=5, options='-c default_transaction_read_only=on') as conn:
        identity = conn.execute('SELECT current_database(), inet_server_addr()::text, inet_server_port()').fetchone()
        require(identity == ('vervfy_passkey_e2e', container_identity[1], 5432), 'Database identity mismatch')
        require(conn.execute('SHOW transaction_read_only').fetchone() == ('on',), 'Inspection transaction is not read-only')
        verify_pg_connections(conn, nat_mapping)
        require(conn.execute('SELECT version_num FROM alembic_version').fetchall() == [('0028_webauthn_enrollment',)], 'Schema revision not verified; no automatic migration')
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        import passkey_schema  # metadata only
        for table in (*passkey_schema.TABLES, passkey_schema.enrollments):
            columns = {r[0] for r in conn.execute('SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s', ('public', table.name))}
            require(set(table.c.keys()) <= columns, f'Missing schema columns: {table.name}')
            rls = conn.execute('SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = %s::regclass', ('public.' + table.name,)).fetchone()
            require(rls == (True, True), f'Forced RLS not verified: {table.name}')
        require(backend_connections(backend) == (pg_ports, redis_ports),
                'Backend connections changed during inspection; retry preflight')
        require(postgres_container() == container_identity, 'PostgreSQL container changed during verification')
        require(postgres_nat_mapping(pg_ports, container_identity[1]) == nat_mapping,
                'PostgreSQL NAT mappings changed during verification')
        conn.execute('SELECT pg_stat_clear_snapshot()')
        verify_pg_connections(conn, nat_mapping)
    client = redis.Redis.from_url(env['REDIS_URL'], socket_connect_timeout=5, socket_timeout=5)
    try:
        clients = client.client_list()
        for port in redis_ports:
            matches = [c for c in clients if c['addr'] == f'127.0.0.1:{port}']
            require(len(matches) == 1 and str(matches[0]['db']) == '1', 'Backend Valkey selected DB cannot be verified')
    finally:
        client.close()
    require(backend.is_running() and frontend.is_running() and caddy.is_running(), 'Service process exited during preflight')
    print('Isolation preflight passed (read-only).')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- fail closed without leaking credentials
        # Never emit connection strings or passwords through dependency exceptions.
        print(f'Preflight blocked: {str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__}', file=sys.stderr)
        sys.exit(1)
