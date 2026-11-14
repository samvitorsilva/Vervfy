# Confirmed catalog findings — preparation only

Decision: NO-GO. No hosted access or SQL execution, permissions/role changes, migrations, support messages or deployment performed. Frozen candidate unchanged. This assessment uses both complete catalog reports supplied by the user.

## Constraint comparison

Candidate 0014_user_covers_remove_artist_catalog.py defines:
`cover_source IN ('embedded', 'user', 'placeholder', 'unknown')`.
0025 drops ck_tracks_cover_source by name, makes cover_source nullable and recreates it accepting NULL or embedded/upload/user/musicbrainz/audiodb/generated/placeholder/unknown. The legacy set is a subset of the target set.

The follow-up's exact expected deparser text hashes locally to MD5 `17ac48241b3e6140aae215970101a9e6`. The first report's tracks CHECK fingerprint was `3420ce3871f3c7503c201b7f9b01b729`; it does not match. The second report now identifies that same fingerprint as ck_tracks_cover_source, validated=true; the mismatch is confirmed and stable across both inspections. These hashes are of deparsed definitions, not migration source code. Formatting/casts/order or a genuinely different accepted-value set can all produce a mismatch; MD5 is only a comparison aid, not proof of semantics. No PostgreSQL reconstruction was executed.

Status: **PASS — accepted-value semantics only**, based on the authorized PostgreSQL 17.11 catalog result supplied by the operator. It reports a validated CHECK on nullable `public.tracks.cover_source` (varchar(20)), accepting NULL and exactly the eight non-NULL values `upload`, `embedded`, `musicbrainz`, `audiodb`, `generated`, `user`, `placeholder`, and `unknown`. Frozen 0025 accepts NULL or exactly the same eight values. The reported deparsed `IS NULL OR ... = ANY(ARRAY[...])` form is consistent with PostgreSQL normalization of the source `IN (...)` expression; array ordering/casts/text representation do not change this set comparison. Therefore current constraint acceptance is equivalent to 0025 acceptance. This does not establish migration operational safety, target identity, absence of other dependencies, or recovery readiness. No production connection or SQL execution was performed in this review; the catalog evidence is operator-supplied.

## Exact extension result

0027 _fresh_privileges scans pg_class joined to pg_namespace, excluding only schema names beginning pg_ and information_schema. `extensions` is included. For relation kinds r/p/v/m/f it calls has_table_privilege(role,oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') OR has_any_column_privilege(...). Any listed privilege suffices. There is no schema-USAGE condition in this branch. Consequently the confirmed PUBLIC SELECT on both extension relations reaches every new role and rejects all three fresh storage roles. Lack of extensions USAGE, NOINHERIT, RLS or an individual REVOKE from those roles cannot cancel PUBLIC privileges.

This is a confirmed hard blocker for the unchanged 0027, not merely an inspector-contract issue. Do not exempt extensions, remove the extension, revoke provider-managed privileges without approval, or weaken the predicate. Provider support must confirm an acceptable object-specific ACL arrangement; if it cannot, migration readiness cannot be reached on this configuration with this candidate.

## Minimal object-specific remediation plan (requires separate approval)

| Object/principal | Proposed change after dependency approval | Migration handling |
|---|---|---|
| public.alembic_version / app_runtime | Remove direct relation privileges and any explicit column privileges; no runtime access needed. Preserve migration-owner authority. | Not corrected by 0020–0027. |
| public.alembic_version / anon, authenticated, service_role | Remove their broad grants on this table only, (no explicit column grants were reported); verify no inherited route restores access. | Not corrected. |
| public.artist_images and public.track_cover_cache / anon, authenticated, service_role | Remove their grants on these two application caches if no explicitly authorized API consumer needs them. Where a documented read consumer exists, approve only SELECT for that consumer instead of broad rights. Do not change those roles globally or touch auth/storage objects. | 0026 does not remove these roles' grants. |
| Same caches / app_runtime | Leave normalization to 0026: SELECT/INSERT/UPDATE retained, direct DELETE and other excess direct privileges removed. | Automatic for the observed state: the complete ACL report contains no PUBLIC or column ACL entries on these tables, and app_runtime cannot inherit or SET any other listed grantee. The earlier suspected PUBLIC-derived cache DELETE path is cleared. |
| app_runtime attribute | Set NOINHERIT; preserve its legitimate direct application grants. | Manual prerequisite; 0027 rejects current attribute. |
| Two named extensions relations / PUBLIC | Provider-supported object-specific removal only if monitoring access can be preserved explicitly and extension-upgrade persistence addressed. | Not corrected; provider approval required. |
| Six capabilities and memberships | Exact graph in support-request.md, provider-supported provisioning with no residual automatic creator edges. | Manual prerequisite; roles are never created by these migrations. |

No CASCADE, blanket schema revocation, provider-role alteration, or deletion of objects is proposed. Capture exact before ACLs/grantors/grant options for recovery; recovery that restores an exposure requires an explicit rollback decision. Check effective privileges after the approved patch. Do not confuse grants to named API roles with PUBLIC grants.

## Preventing unwanted provider_identities grants

The report confirms service_role has BYPASSRLS; anon/authenticated do not. The confirmed defaults belong to postgres and apply to future public tables. 0021 would inherit them; 0024 only changes app_runtime's ACL. Existing RLS is not sufficient justification for leaving broad grants, particularly for service_role. A revoke after a separately committed migration allows an exposure interval and is not acceptable.

Smallest unchanged-candidate option: after explicit approval, in a serialized application-DDL maintenance window, snapshot the exact postgres/public TABLE default ACL entries to anon/authenticated/service_role, suppress only those entries before migration, verify suppression, migrate with the approved postgres identity, verify the new table ACL, then restore precisely the original default entries after the migration has committed. Restoring defaults does not backfill privileges on the existing provider_identities table. Existing objects and auth/storage schemas are unaffected by default-ACL changes; nevertheless concurrent public object creation must be excluded and platform compatibility confirmed. Retain unrelated defaults. The complete report shows postgres/public entries only, no global default entries or PUBLIC default grants. This resolves the previously masked fourth recipient as postgres itself. A per-schema revoke could not counter a global grant if one is introduced later. Stop if any additional grant source or DDL event trigger could regrant access without an approved resolution.

This is a non-atomic multi-step operations plan, not ready-to-run SQL. On failure, stop and assess transaction/revision state before restoring defaults; never continue deployment. An atomic migration wrapper could alternatively create and strip table ACLs before commit, but the frozen alembic/env.py opens its own connection and does not accept an externally supplied transaction. Do not claim an outer SQL Editor BEGIN wraps the Alembic process. Such a wrapper requires separate local validation and approval. A dedicated migration owner avoids postgres defaults only with additional ownership/authority work and is not the smallest current change.

## Status and shortest path

PASS: five types; seven trusted RLS predicates; expected constraint name/validation. UNKNOWN: actual constraint semantics; provider provisioning/extension ACL support; API/cache consumer dependencies; possible creation-time regrant mechanisms. FAIL: runtime revision-table ACL and INHERIT; unwanted named-role grants pending approved access requirements; six missing roles; PUBLIC extension SELECT against the exact 0027 guard; unsafe future identity-table grants without containment.

1. Resolve ONLY the known constraint's semantics through privately reviewed catalog-definition evidence; no broad inspection rerun.
2. Authorized owner sends the prepared support enquiry. Resolve both the membership graph and extension PUBLIC ACL compatibility before any role creation or migration preparation changes.
3. Approve the exact three-application-table ACL patch, app_runtime attribute change, provider extension action and default-ACL containment window. Confirm cache consumers and choose migration identity.
4. Separately approve provider role provisioning and establish the exact graph. Confirm role/object privileges and ACL/default postconditions through a narrow approved read-only check; all 0022/0027 predicates must pass.
5. With recovery evidence and the constraint check satisfied, separately approve migration to exactly 0027_storage_lifecycle, including the default-ACL suppression/verification/restoration sequence. Verify revision and identity-table ACLs before any deployment approval. Keep 0028 unapplied and physical deletion disabled.

Next action: await Supabase's already-requested confirmation of role provisioning and extension ACL compatibility. Separately retain the outstanding production recovery gate: an authorized database plus object-storage backup must be independently restored and checked in an isolated environment. Do not proceed to migration approval until provider compatibility, remaining role/ACL/default-ACL gates, and recovery evidence are resolved. No production changes are authorized by this assessment.

References: PostgreSQL 17 ALTER DEFAULT PRIVILEGES https://www.postgresql.org/docs/17/sql-alterdefaultprivileges.html ; role attributes https://www.postgresql.org/docs/17/role-attributes.html ; Supabase superuser restrictions https://supabase.com/docs/guides/database/postgres/roles-superuser . Provider ability to fulfill the request is unconfirmed.
