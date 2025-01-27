from unittest.mock import mock_open, patch
import pytest
from unified_config.core.data_conversion import (
    load_config_file,
    save_config_file,
    convert_config,
)


@pytest.mark.parametrize(
    "file_content, file_ext, expected_output",
    [
        ('{"key": "value"}', ".json", {"key": "value"}),  # JSON file
        (
            "key: value\nlist:\n  - item1\n  - item2",
            ".yaml",
            {"key": "value", "list": ["item1", "item2"]},
        ),  # YAML file
        (
            'key = "value"\n[list]\nitem1 = "data"',
            ".toml",
            {"key": "value", "list": {"item1": "data"}},
        ),  # TOML file
    ],
)
def test_load_config_file(file_content, file_ext, expected_output):
    """Test loading JSON, YAML, and TOML config files."""
    with patch("builtins.open", mock_open(read_data=file_content)) as mock_file:
        with patch("os.path.exists", return_value=True):  # Ensure the file exists
            result = load_config_file(f"config{file_ext}")
            assert result == expected_output
            mock_file.assert_called_once_with(f"config{file_ext}", "r")


@pytest.mark.parametrize(
    "data, file_ext, expected_content",
    [
        ({"key": "value"}, ".json", '{\n    "key": "value"\n}'),  # JSON output
        ({"key": "value"}, ".yaml", "key: value\n"),  # YAML output
        ({"key": "value"}, ".toml", 'key = "value"\n'),  # TOML output
    ],
)
def test_save_config_file(data, file_ext, expected_content):
    """Test saving JSON, YAML, and TOML files."""
    with patch("builtins.open", mock_open()) as mock_file:
        save_config_file(f"config{file_ext}", data)

        # Aggregate all write() calls into a single string
        written_data = "".join(
            call.args[0] for call in mock_file().write.call_args_list
        )

        assert written_data.strip() == expected_content.strip()


@pytest.mark.parametrize(
    "data, fmt, expected_output",
    [
        ({"key": "value"}, "json", '{\n    "key": "value"\n}'),  # JSON
        ({"key": "value"}, "yaml", "key: value\n"),  # YAML
        ({"key": "value"}, "toml", 'key = "value"\n'),  # TOML (dict)
        # Ensure TOML lists are formatted correctly (Multi-line)
        (
            ["item1", "item2"],
            "toml",
            '[config_list]\nconfig_list = [\n    "item1",\n    "item2"\n]\n',
        ),
        # Ensure single-string TOML formatting
        ("exported_value", "toml", '[config_value]\nconfig_value = "exported_value"\n'),
    ],
)
def test_convert_config(data, fmt, expected_output):
    """Test conversion of config data into different formats."""
    result = convert_config(data, fmt).strip()
    assert (
        result == expected_output.strip()
    ), f"Expected:\n{expected_output}\nGot:\n{result}"


def test_convert_config_unsupported_format():
    """Test that an unsupported format raises an error."""
    with pytest.raises(ValueError, match="Unsupported format"):
        convert_config({"key": "value"}, "xml")  # ❌ Unsupported format


def test_convert_config_invalid_format():
    """Test converting to an unsupported format."""
    with pytest.raises(ValueError, match="Unsupported format"):
        convert_config({"key": "value"}, "xml")  # XML is unsupported


def test_load_config_file_invalid_format():
    """Test loading an unsupported file format."""
    with patch("builtins.open", mock_open(read_data="dummy")), pytest.raises(
        ValueError, match="Unsupported config file format"
    ):
        load_config_file("config.txt")  # .txt is unsupported


def test_save_config_file_invalid_format():
    """Test saving to an unsupported file format."""
    with pytest.raises(ValueError, match="Unsupported config file format"):
        save_config_file("config.txt", {"key": "value"})  # .txt is unsupported


def test_load_config_file_unsupported_format(mocker):
    """Test that an unsupported config file format raises an error."""
    mocker.patch("builtins.open", mock_open(read_data="invalid_data"))
    with pytest.raises(ValueError, match="Unsupported config file format"):
        load_config_file("config.txt")  # ❌ Unsupported format
