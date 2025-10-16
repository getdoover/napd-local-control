"""
Basic tests for an application.

This ensures all modules are importable and that the config is valid.
"""

def test_import_app():
    from napd_local_control.application import NapdLocalControlApplication
    assert NapdLocalControlApplication

def test_config():
    from napd_local_control.app_config import NapdLocalControlConfig

    config = NapdLocalControlConfig()
    assert isinstance(config.to_dict(), dict)
