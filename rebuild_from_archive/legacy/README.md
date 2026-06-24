# Legacy

This directory keeps runtime-accessible compatibility entrypoints that still
exist for backward compatibility or manual workflows.

Current contents:

- `data_api_legacy.py`: archived parallel `DataAPI` implementation that is still
  re-exported by the public `rebuild_from_archive/data_api.py` shim.

Known callers:

- `rebuild_from_archive/data_api.py` public shim.

Cleanup criteria:

- all callers have moved to `rebuild_from_archive/engine/data_api.py` or another
  maintained entrypoint;
- the `rebuild_from_archive/data_api.py` shim is deleted;
- no tooling or manual workflow still depends on the legacy import path.
