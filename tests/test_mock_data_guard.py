import importlib
import os
import sys


def test_mock_data_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("USE_MOCK_DATA", raising=False)
    shared = importlib.import_module("shared")
    assert shared.is_mock_data_enabled() is False


def test_real_job_processing_path_does_not_import_mock_module(monkeypatch):
    monkeypatch.delenv("USE_MOCK_DATA", raising=False)
    sys.modules.pop("shared.mock_data", None)
    sys.modules.pop("backend.main", None)
    sys.modules.pop("pipeline.ingest", None)

    importlib.import_module("backend.main")
    importlib.import_module("pipeline.ingest")

    assert "shared.mock_data" not in sys.modules
