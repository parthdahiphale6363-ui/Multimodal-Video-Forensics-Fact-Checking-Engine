import os


def is_mock_data_enabled() -> bool:
    return os.getenv("USE_MOCK_DATA", "false").lower() in {"1", "true", "yes", "on"}
