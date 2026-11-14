"""Exact PostgreSQL 17 membership checks for Supabase-created roles."""

import sqlalchemy as sa

PROVIDER_CREATOR = "postgres"
PROVIDER_GRANTOR = "supabase_admin"
PROVIDER_OPTIONS = (True, False, False)


def _role_oid(bind, name):
    oid = bind.execute(
        sa.text("SELECT oid FROM pg_catalog.pg_roles WHERE rolname=:name"),
        {"name": name},
    ).scalar_one_or_none()
    if oid is None:
        raise RuntimeError(f"Required Supabase role {name} is missing")
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
    result = {}
    for name in names:
        result[name] = _role_oid(bind, name)
    return result


def assert_role_memberships(bind, role_name, explicit_memberships):
    """Require the exact grants plus only Supabase's non-inheriting creator edge."""
    names = {role_name, PROVIDER_CREATOR, PROVIDER_GRANTOR}
    for member_name, grantor_name, *_ in explicit_memberships:
        names.update((member_name, grantor_name))
    role_ids = _role_oid_map(bind, names)
    expected = {
        (
            role_ids[PROVIDER_CREATOR],
            role_ids[PROVIDER_GRANTOR],
            *PROVIDER_OPTIONS,
        )
    }
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
    actual = _membership_rows(bind, roleid=role_ids[role_name])
    if len(actual) != len(expected) or set(actual) != expected:
        raise RuntimeError(
            f"Unexpected membership graph for {role_name}; "
            "only the exact Supabase creator edge and reviewed grants are allowed"
        )


def assert_member_memberships(bind, member_name, explicit_memberships):
    """Require a member role's exact outgoing grants, including grantor/options."""
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
