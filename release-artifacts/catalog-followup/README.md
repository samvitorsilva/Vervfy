# Narrow production catalog follow-up — review only

Decision: NO-GO pending the metadata delta and a provider-supported provisioning path. No production connection, SQL execution, role/permission changes, migrations or deployment were performed. The release candidate and restricted-inspector runner are unchanged.

Target: Supabase project `llxmskxxchpmeavorusj`, database `postgres`, authorized project-owner operator using `postgres`, PostgreSQL 17.11. Reported baseline: `dd22f18b92e26a59d342a98e06dfc2888c58905b`; observed revision `0019_track_listens`; sole intended target `0027_storage_lifecycle`. This follow-up deliberately does not repeat version/revision/RLS-flag inventories or verify the Render deployment.

## Exact next operator action and inspection approval

Review `production-catalog-followup.sql` and `SHA256SUMS`. Obtain separate explicit approval for this one-time metadata-only inspection. Verify the project reference in the Supabase dashboard (SQL cannot authenticate that project reference), then use SQL Editor as the already authorized owner to run the ENTIRE file, including BEGIN and ROLLBACK. Do not use the application credential or a service-role key. Do not run selected statements. On any error, timeout, wrong database/operator/version, STOP; if a transaction remains open, execute only ROLLBACK. Never repair permissions inside this inspection.

Local integrity command, from the repository root:

```sh
(cd release-artifacts/catalog-followup && sha256sum -c SHA256SUMS)
```

Share only `followup_report`, the verified script hash and execution time with authorized release reviewers. It contains internal security metadata, including previously masked database-role names; review it privately before sharing. Do not share credentials, editor/session screenshots, raw errors, connection strings or tokens.

## What the SQL establishes

- `acl_provenance`: explicit/default relation ACLs and column ACLs for ONLY alembic_version and the two shared caches, with grantors, grantees and runtime inheritance/SET reachability. Ownership remains a separate privilege source. PUBLIC access cannot be negated by revoking an individual role.
- `default_acl_provenance`: exact grantees for postgres global/public defaults, plus PUBLIC default ACL entries anywhere (the latter are rejected by 0027). Identify grantee BYPASSRLS/superuser attributes and inspect relevant membership edges. These are actual default entries; implicit PUBLIC function EXECUTE is separately accounted for in the obstacle query. If a different migration identity is chosen, its defaults must be assessed before approval.
- `relevant_memberships`: grantor and exact ADMIN/INHERIT/SET flags for operator/runtime and recipients of those defaults. This does not certify an arbitrary future role graph or every transitive path; after provision, validate the exact candidate guard predicates against actual roles.
- `column_types`: last_played_at should be nullable double precision; cover_url nullable text; cover_data nullable bytea. Also reports cover_source (candidate expects varchar(20)) and password_hash. Existing last_played_at/cover_url/cover_data are skipped, not corrected, by 0020/0023. 0021 makes password_hash nullable; 0025 makes cover_source nullable.
- `cover_constraint`: exact constraint name, validation status and definition fingerprint. The known legacy expression from candidate 0014 allows embedded/user/placeholder/unknown. The literal comparison is a conservative PostgreSQL deparser-form check, not a semantic parser. False means review needed, not proof of unsafe values. A validated matching legacy constraint admits only values retained by 0025. Unexpected/unvalidated constraints cannot establish data compatibility from metadata alone.
- `rls_fingerprints`: exact policy identity, predicate hashes, equality of USING/WITH CHECK and conservative comparisons to known tenant predicates from 0007/0008/0015/0019. Formatting, casts and qualification can make comparisons false. Do not approve a fingerprint merely because it repeats the previously reported hash. Unmatched forms require a separately reviewed, private metadata-expression comparison; do not export arbitrary policy expressions or query tenant records. Confirm every policy on a table is accounted for; an extra permissive policy changes effective access.
- `public_fresh_role_obstacles`: only PUBLIC exposures relevant to the exact 0027 fresh-role checks, including implicit ACL defaults: non-system relations/columns/sequences, schema CREATE, and routine EXECUTE where PUBLIC also has schema USAGE. Any returned exposure blocks a fresh isolated storage role. PUBLIC TEMP and pg_catalog large-object functions are deliberately excluded because 0027 does not test them. This is not a complete substitute for checks on the actual provisioned roles.

The script uses BEGIN READ ONLY, pg_catalog search_path, 30s statement timeout, 3s lock timeout, 60s idle transaction timeout and ROLLBACK. The anonymous guard reads catalogs and raises exceptions only. All report queries read pg_catalog; no application table rows, credentials, password fields, function bodies or raw predicate text are returned. Built-in metadata/deparser/privilege functions are used; application functions are never called. There are no temporary tables, persistent objects, writes or maintenance commands. A read-only transaction limits this operation; it does not make the elevated operator a restricted identity.

## Role provisioning conclusion

PostgreSQL 17 can represent the required graph. Ordinary non-superuser CREATEROLE provisioning cannot by itself produce it: PostgreSQL adds a bootstrap-granted creator ADMIN membership that the creator cannot remove or change. This conflicts with forbidden inbound memberships on the login/executor roles and the storage owner's required ADMIN=false edge. NOINHERIT or createrole_self_grant settings do not remove this automatic ADMIN grant. Do not try intermediary creators, temporary privileged roles, SET ROLE escalation or relaxed migration guards.

Supabase documents that customer postgres is not superuser. Therefore the safe path is **provider-assisted provisioning or a documented provider-supported mechanism with equivalent authority**, confirmed by Supabase for this project. Request confirmation that it can create the six roles without unwanted creator edges, or remove those bootstrap-granted edges and establish the exact final graph. Availability is UNKNOWN; no support message has been sent and no provider promise is inferred from generic documentation. If Supabase cannot support this graph, the unchanged candidate remains NO-GO on this configuration.

Sources:
- https://www.postgresql.org/docs/17/role-attributes.html (automatic creator grant and superuser authority; search result excerpt also states the bootstrap-grant removal restriction)
- https://www.postgresql.org/docs/17/role-membership.html
- https://supabase.com/docs/guides/database/postgres/roles-superuser

## Ordered remediation plan — NOT execution authorization

1. **Inspection approval:** obtain and review the narrow follow-up above. Stop on any unclassified exposure, unexpected schema shape, or unsupported provisioning authority. Do not repeat the broad inspection.
2. **Authority decision:** nominate the migration identity M. Existing postgres owns the application tables and has database/public CREATE, making it the smallest ownership-change option, but its use needs explicit approval. A different M needs separately reviewed DDL, revision-write, grant and ownership-transfer authority and its own default-ACL analysis. Obtain provider confirmation before creating any role.
3. **Permission-change approval:** approve an exact provenance-based patch: set app_runtime NOINHERIT; remove its unnecessary alembic_version access at the actual source, including column grants if applicable. For application-owned cache/PUBLIC/default grants, approve only the precise changes needed after identifying affected consumers. Do not blanket-revoke provider-managed PUBLIC privileges. If provider-managed exposure conflicts with 0027 and cannot be resolved through a supported approved change, STOP. Existing migrations do not solve that conflict.
4. **Default-ACL approval:** ensure newly created provider_identities will not receive unintended grants from M's defaults. 0024 removes only runtime grants and does not clean grants to those four other recipients. Plan an explicitly scoped default-privilege correction or approved migration-session containment before table creation; any temporary change and restoration must itself be reviewed. Do not assume RLS neutralizes a BYPASSRLS grantee. Do not edit the validated candidate ad hoc.
5. **Provider provisioning approval:** provider-supported creation of the six roles, with NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT on all. The identity and storage owner/executor roles are NOLOGIN; google_auth_lookup and storage_cleanup_worker are LOGIN. Do not distribute login credentials yet. Secure credential issuance/rotation is a separate approved operation through an approved secret channel, never SQL shared in this report.
6. **Exact final graph:** owner roles have no outbound memberships. Only M holds the identity owner; give M INHERIT=false, SET=true, ADMIN=false (0022 checks membership/isolation; SET supports ownership transfer). Storage owner has exactly one inbound edge, from M with those same flags. Identity executor has exactly one inbound edge from google_auth_lookup; storage executor exactly one from storage_cleanup_worker; both edges INHERIT=true, SET=false, ADMIN=false. Executors have no outbound memberships. Both service logins have only their executor membership and no inbound members. Runtime has no outbound membership. No unexpected effective non-superuser USAGE/SET access may exist. Remove residual automatic creator grants using provider authority; do not retain extra ADMIN edges. All three storage roles must arrive without preexisting unrelated privileges/ownership/default ACLs. M needs CONNECT, database CREATE, public USAGE/CREATE, current_schema public, affected-table DDL/revision authority, grant authority and function ownership-transfer authority. The migrations grant the narrow object privileges themselves; do not pregrant storage roles reference/table privileges before 0027's fresh-role check.
7. **Verification approval:** perform a separately approved metadata-only verification of changed attributes/ACLs and the exact 0022/0027 graph/fresh-role predicates. Confirm new grants/defaults do not recreate exposure. A provider confirmation alone is not this verification.
8. **Migration approval:** only after those checks and existing backup/restore evidence gates pass, seek separate approval for the frozen candidate's migration to exactly 0027_storage_lifecycle. No head upgrade, 0028, physical deletion, deployment or OAuth enablement is authorized by this document. Schema discrepancies requiring code changes invalidate this preparation path and require a separately validated candidate.

## Automatic versus manual

| Finding | Migration behavior / required preparation |
|---|---|
| Six absent roles; automatic creator edges | Manual/provider prerequisite before 0022/0027; migrations do not provision roles. |
| Runtime INHERIT | Manual attribute correction; 0027 rejects it. |
| Runtime alembic_version access | Manual source-specific ACL correction; 0026 excludes this table. |
| Direct runtime DELETE on caches | 0026 revokes direct table/column privileges and grants only SELECT/INSERT/UPDATE. PUBLIC/inherited DELETE requires manual approved correction. |
| Four default-ACL recipients | Manual investigation/containment; 0024 does not remove their provider_identities grants. |
| PUBLIC exposures of fresh storage roles | Manual/provider compatibility gate; 0027 rejects them before creating its schema. |
| Missing identity/lifecycle tables/functions | Created by 0021/0022/0027 after prerequisites pass. |
| Existing column type mismatch | Not repaired by 0020/0023 when columns already exist; stop for a reviewed resolution. |
| Correct legacy cover-source constraint | 0025 replaces it and allows NULL; missing name or incompatible existing values is not automatically repaired. |
| Existing tenant RLS drift | Not repaired by this migration chain; unexpected fingerprints/policies need review. |

Validation: static local review only; no SQL executed locally or remotely. Python SQL parser pglast is unavailable, so PostgreSQL grammar/runtime validation is not claimed. The hash identifies the reviewed bytes, not a successful production run. Outcomes requiring follow-up results remain UNKNOWN.
