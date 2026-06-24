"""Compatibility shim for the archived legacy DataAPI implementation.

The actual legacy implementation has been moved to
`rebuild_from_archive/suspected_unused/data_api_legacy.py` so suspected-unused
artifacts can stay centralized before final cleanup.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_LEGACY_PATH = Path(__file__).with_name('suspected_unused') / 'data_api_legacy.py'
_SPEC = spec_from_file_location('rebuild_from_archive.suspected_unused.data_api_legacy', _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f'Unable to load legacy DataAPI module: {_LEGACY_PATH}')

_module = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_module)

JQMockResult = _module.JQMockResult
SecurityInfo = _module.SecurityInfo
DataAPI = _module.DataAPI

__all__ = ['JQMockResult', 'SecurityInfo', 'DataAPI']
