# Documentation cleanup verification

Updated the staging approval package and candidate staging proposal with neutral workspace wording. Three affected archive/manifest pairs were regenerated. Each manifest entry was verified against its archive; the staging proposal is the only archive member whose contents changed. SQL, configuration, identifiers, credentials, and application files are unchanged. No hosted operations were performed.

Changed documentation:
- `docs/staging-deployment-approval-package.md`
- `release-artifacts/supabase-pg17-oauth-rc/source/docs/render-staging-proposal.md`

Changed release artifacts and verified SHA-256 hashes:

- `release-artifacts/supabase-pg17-oauth-rc/vervfy-supabase-pg17-oauth-rc-virginia-staging-runtime-guard.tar.gz`
  `aa109740381cc3abb0c9e3690c1ff7f60d04ccfd11bec4a71d62ec2d48aefa23`
- `release-artifacts/supabase-pg17-oauth-rc/candidate-manifest-virginia-staging-runtime-guard.json`
  `4080312c91e5737fc815d38d8a5f7612aca32fa82a3f51edfb8a7fe079ed8aa9`
- `release-artifacts/supabase-pg17-oauth-rc/vervfy-supabase-pg17-oauth-rc-virginia-staging.tar.gz`
  `eb14fdde5a56cb736da09acb900ca482e06b31e1a74fd4f2e9f1cf22221f14a7`
- `release-artifacts/supabase-pg17-oauth-rc/candidate-manifest-virginia-staging.json`
  `cd690d9452e420e8eaa789283d83864319240244bea262ba73cc4f4b48a55433`
- `release-artifacts/supabase-pg17-oauth-rc/vervfy-supabase-pg17-oauth-rc-virginia.tar.gz`
  `5de702987ac87595369905d1d6caf964a35a72d8adbe3ee8f47ccbbdf55d12c0`
- `release-artifacts/supabase-pg17-oauth-rc/candidate-manifest-virginia.json`
  `5eb6aa947f3c471088e12c7939bdb0baeec33bb1b26888464a516665e54e3934`

Concurrent edits changed the working staging proposal during cleanup. Those edits were preserved, and their additional personal-name references were neutralized. The regenerated archives preserve their respective original snapshots apart from the wording cleanup; the working source has separate concurrent changes.
