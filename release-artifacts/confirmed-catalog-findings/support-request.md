Subject: Supported restricted-role provisioning and extension ACL compatibility — project llxmskxxchpmeavorusj / PostgreSQL 17.11

We are preparing an application migration from 0019_track_listens through 0027_storage_lifecycle. No changes are requested or authorized by this enquiry. Our SQL Editor postgres role is not superuser. Please confirm a supported mechanism, required approvals and operational impact for the following exact constraints.

Six roles are currently absent. All must be NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT:
- NOLOGIN: vervfy_identity_lookup_owner, vervfy_identity_lookup, vervfy_storage_lifecycle_owner, vervfy_storage_cleanup.
- LOGIN: google_auth_lookup, storage_cleanup_worker.

For an explicitly approved migration identity M (postgres is the existing application-table owner and proposed smallest-change choice):
- M is the only member of either owner role, with INHERIT false, SET true, ADMIN false. Owner roles have no outbound memberships.
- google_auth_lookup is the sole member of vervfy_identity_lookup, with INHERIT true, SET false, ADMIN false.
- storage_cleanup_worker is the sole member of vervfy_storage_cleanup, with INHERIT true, SET false, ADMIN false.
- Executors have no outbound memberships. Each service login has only its executor membership and has no inbound memberships. No other non-superuser may effectively inherit or SET the protected capabilities.
- Existing app_runtime must be NOINHERIT and have no outbound memberships.
- No residual creator ADMIN memberships are permitted on these six roles. PostgreSQL 17 automatically grants a non-superuser creator a bootstrap-granted ADMIN edge; ordinary creator authority cannot remove it.

Can Supabase provision this exact graph directly, or remove/normalize bootstrap-granted creator edges through a supported mechanism? Please specify the responsible authority and verification method without granting customer superuser access. Please also confirm M can transfer SECURITY DEFINER function ownership to the owner roles with these memberships. We will not relax application migration guards or use privileged workarounds.

Separately, PUBLIC SELECT is present on extensions.pg_stat_statements and extensions.pg_stat_statements_info. Our migration rejects any non-system relation SELECT privilege for the three fresh storage roles, regardless of schema USAGE. PUBLIC grants necessarily reach those roles. Is there a supported object-specific way to remove these two PUBLIC grants while preserving required Supabase monitoring access via explicit service-role grants? Who owns/manages these ACLs, what consumers depend on them, and can extension updates recreate them? If this is unsupported, please confirm the incompatibility. No blanket PUBLIC revocation or extension removal is proposed.

Please also confirm whether application-owned public.alembic_version, public.artist_images and public.track_cover_cache require any anon/authenticated/service_role access for platform services independent of our app, and whether temporarily suppressing ONLY postgres/public TABLE default grants to those three roles during a serialized application-DDL window is supported. Existing auth/storage schema grants would remain unchanged.

Please provide guidance only; role creation, permissions changes and migrations require our separate explicit approval. No credentials, user records or music objects are included or needed.
