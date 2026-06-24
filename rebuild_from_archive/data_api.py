"""Compatibility shim for the archived legacy DataAPI implementation.

This public entrypoint remains available for legacy callers, but the archived
implementation now lives under `rebuild_from_archive/legacy/` instead of the
suspected-unused bucket.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_LEGACY_PATH = Path(__file__).with_name("legacy") / "data_api_legacy.py"
_SPEC = spec_from_file_location("rebuild_from_archive.legacy.data_api_legacy", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load legacy DataAPI module: {_LEGACY_PATH}")

_module = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_module)

JQMockResult = _module.JQMockResult
SecurityInfo = _module.SecurityInfo
DataAPI = _module.DataAPI

__all__ = ["JQMockResult", "SecurityInfo", "DataAPI"]
