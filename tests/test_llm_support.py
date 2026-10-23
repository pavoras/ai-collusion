"""Workspace-local disposable data for sandboxed offline tests."""

from pathlib import Path
import tempfile

import pytest
from collusion.llm.runner import RunConfig as CollectionConfig


def run_config(**kwargs):
    """Legacy unit scenarios are explicitly segregated from declared collection."""
    return CollectionConfig(deviation_cohort="tests", deviation_reason="Offline unit-test scenario", **kwargs)


@pytest.fixture
def tmp_path():
    """Avoid a pre-existing system pytest temp folder with restricted Windows ACLs."""
    workspace = Path(__file__).resolve().parents[1]
    parent = workspace / "results" / "raw" / "llm_test_temp"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="test_", dir=parent) as folder:
        path = Path(folder).resolve()
        assert workspace in path.parents
        yield path
