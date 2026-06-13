import os
import sys
import io
from unittest import mock

try:
    import pytest
except ImportError:
    class MockPytest:
        class RaisesContext:
            def __init__(self, expected_exception):
                self.expected_exception = expected_exception
                self.value = None
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    raise AssertionError(f"Did not raise {self.expected_exception}")
                if issubclass(exc_type, self.expected_exception):
                    self.value = exc_val
                    return True
                return False
        def raises(self, expected_exception):
            return self.RaisesContext(expected_exception)
    pytest = MockPytest()
from tlnw_tools.cli import find_tools_config, load_tools_config, is_package_installed, main

def test_find_tools_config():
    config_path = find_tools_config()
    assert config_path is not None
    assert os.path.exists(config_path)
    assert config_path.endswith("tools.yml")

def test_load_tools_config():
    config = load_tools_config()
    assert isinstance(config, dict)
    assert "tools" in config
    assert isinstance(config["tools"], list)
    
    # Ensure our first tool is registered
    generate_image_tool = next((t for t in config["tools"] if t["name"] == "generate-image"), None)
    assert generate_image_tool is not None
    assert generate_image_tool["package"] == "tlnw-generate-image"
    assert generate_image_tool["execution_mode"] == "inprocess_import"

def test_is_package_installed():
    # 'yaml' should be installed as it's a dependency
    assert is_package_installed("yaml") is True
    # 'sys' is built-in
    assert is_package_installed("sys") is True
    # A random fake package name should not be installed
    assert is_package_installed("non_existent_fake_package_xyz123") is False

def test_cli_help_stdout():
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        with mock.patch.object(sys, 'argv', ['tlnw-tools', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        captured = mock_stdout.getvalue()
    assert "Usage: tlnw-tools" in captured
    assert "generate-image" in captured

def test_cli_invalid_tool():
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        with mock.patch.object(sys, 'argv', ['tlnw-tools', 'non-existent-tool']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        captured = mock_stdout.getvalue()
    assert "Error: Tool 'non-existent-tool' not registered" in captured
