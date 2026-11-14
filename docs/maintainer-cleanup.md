# Maintainer cleanup and credential incident

## Changes in this cleanup

- Removed `.env`, generated SQLite state, CPython bytecode, the Office lock file, the obsolete hackathon deck, and the stale implementation plan from the current tree.
- Added ignore rules, a placeholder-only configuration template, pinned dependencies, offline regression tests, a credential-pattern guard, and CI.
- Replaced global chat/router state with request-owned state; cloud use requires operator and client opt-in. Explicit local routing cannot send to cloud.
- Restricted default access to loopback, added optional bearer-token access, bounded inputs, and removed wildcard CORS, shared conversation inspection, and raw error disclosure.
- Labeled the source fixtures and policies as synthetic demo material, documented actual architecture and limitations, and added an MIT license.

## Still requires the credential owner

A Google-format Gemini credential was present in the public initial commit. Its value is intentionally not reproduced. The cleanup does not prove it has been revoked.

1. Revoke the exposed credential in the Google project that owns it. Review usage and billing for unexpected activity. Create a replacement only if cloud processing is needed, and store it outside Git.
2. Removing `.env` from the current tree does not erase the initial commit. Rewrite reachable history to remove sensitive files, coordinate a fresh clone with anyone using the old history, and inspect all branches and tags. Do not keep public backup branches or tags pointing to the compromised commit.
3. GitHub may retain cached commit views or other references after rewriting. Request removal of sensitive cached content through GitHub Support where necessary. History rewriting cannot delete copies already downloaded by others.

A history rewrite changes commit IDs. It is deliberately separate from the normal cleanup commit so the maintainer can review the tested result before replacing public history. For this repository's original single-commit history, a new sanitized root can preserve the complete cleaned tree while dropping the old parent chain. Do not blindly force-push over changes made by another contributor.

`python scripts/scan_secrets.py --history` checks supported credential patterns across locally reachable Git objects. Its default mode scans current tracked files. Neither mode is exhaustive; a clean result is not proof that every possible secret is absent.

## Repository metadata

The connected code tools cannot edit repository administration metadata. With an authenticated GitHub CLI account that has permission, run:

```bash
bash scripts/configure_repository.sh
```

This sets a factual description, relevant topics, and a README homepage. The homepage is documentation, not a claim of a hosted demo.

## Final review

After history cleanup, verify every public branch/tag is sanitized, regenerate the fixture from a fresh clone, install the pinned dependencies, and run:

```bash
python scripts/scan_secrets.py
python scripts/scan_secrets.py --history
python -m pytest -q
```

The discarded deck described a proposed React/PostgreSQL/FAISS/MCP architecture and secure role filtering. It should not be republished as evidence of implemented functionality without correcting those claims and reviewing author/embedded content metadata.
