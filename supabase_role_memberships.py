"""Exact PostgreSQL 16+ checks for restricted application role memberships."""

import sqlalchemy as sa


def _role_oid(bind, name):
    oid = bind.execute(
        sa.text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname=:name"),
        {"name": name},
    ).scalar_one_or_none()
    if oid is None:
        raise RuntimeError(f"Required database role {name} is missing")
    return oid


def _membership_rows(bind, *, roleid=None, member=None):
    predicate = "roleid=:roleid" if roleid is not None else "member=:member"
    value = roleid if roleid is not None else member
    principal = "member" if roleid is not None else "roleid"
    return [
        tuple(row)
        for row in bind.execute(
            sa.text(f"""
                SELECT {principal}, grantor, admin_option, inherit_option, set_option
                FROM pg_catalog.pg_auth_members
                WHERE {predicate}
            """),
            {predicate.split("=")[0]: value},
        ).all()
    ]


def _role_oid_map(bind, names):
    return {name: _role_oid(bind, name) for name in names}


def assert_role_memberships(bind, role_name, explicit_memberships):
    """Require reviewed grants and preserve an optional Supabase-managed edge."""
    names = {role_name}
    for member_name, grantor_name, *_ in explicit_memberships:
        names.update((member_name, grantor_name))
    role_ids = _role_oid_map(bind, names)
    expected = set()
    expected.update(
        (
            role_ids[member_name],
            role_ids[grantor_name],
            admin_option,
            inherit_option,
            set_option,
        )
        for member_name, grantor_name, admin_option, inherit_option, set_option
        in explicit_memberships
    )
    postgres_oid = bind.execute(
        sa.text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname='postgres'")
    ).scalar_one_or_none()
    admin_oid = bind.execute(
        sa.text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname='supabase_admin'")
    ).scalar_one_or_none()
    if postgres_oid is not None and admin_oid is not None:
        managed_rows = _membership_rows(bind, roleid=role_ids[role_name])
        managed_rows = [
            row for row in managed_rows
            if row[0] == postgres_oid and row[1] == admin_oid
        ]
        if managed_rows and managed_rows != [
            (postgres_oid, admin_oid, True, False, False)
        ]:
            raise RuntimeError(
                f"Unexpected Supabase-managed membership options for {role_name}"
            )
        expected.update(managed_rows)
    # Existing production owner-only SET grant; accept exactly this optional edge.
    # Do not extend this exception to executor or login capability roles.
    if role_name == "vervfy_identity_lookup_owner" and postgres_oid is not None:
        owner_admin_edge = (postgres_oid, postgres_oid, False, False, True)
        if owner_admin_edge in _membership_rows(bind, roleid=role_ids[role_name]):
            expected.add(owner_admin_edge)
    actual = _membership_rows(bind, roleid=role_ids[role_name])
    if len(actual) != len(expected) or set(actual) != expected:
        raise RuntimeError(
            f"Unexpected membership graph for {role_name}; only reviewed grants "
            "and an optional Supabase-managed postgres edge are allowed"
        )


def assert_member_memberships(bind, member_name, explicit_memberships):
    """Require the member role's exact outgoing grants and options."""
    names = {member_name}
    for role_name, grantor_name, *_ in explicit_memberships:
        names.update((role_name, grantor_name))
    role_ids = _role_oid_map(bind, names)
    expected = {
        (
            role_ids[role_name],
            role_ids[grantor_name],
            admin_option,
            inherit_option,
            set_option,
        )
        for role_name, grantor_name, admin_option, inherit_option, set_option
        in explicit_memberships
    }
    actual = _membership_rows(bind, member=role_ids[member_name])
    if len(actual) != len(expected) or set(actual) != expected:
        raise RuntimeError(
            f"Unexpected memberships held by {member_name}; "
            "only explicitly reviewed grants are allowed"
        )
