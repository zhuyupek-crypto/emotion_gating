# Suspected Unused

This directory temporarily centralizes legacy artifacts that are not part of the current runtime main path but are being retained until a final cleanup pass.

Current contents:

- `data_api_legacy.py`: archived parallel DataAPI implementation. The original `rebuild_from_archive/data_api.py` path is now a shim that re-exports from this file.
- `core_diff_rebased.patch`
- `core_diff_rebased_git.patch`

Removal criteria:

- yearly parity regression confirms no dependency remains;
- no tooling or manual workflow still imports the legacy DataAPI path;
- patch texts are no longer needed as reference material.
