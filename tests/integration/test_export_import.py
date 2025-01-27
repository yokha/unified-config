import json
import toml
import yaml
import pytest

from unified_config.core.data_conversion import convert_config
from .helpers import flush_redis_cache


@pytest.mark.asyncio
async def test_export_config_raw_dict(config_manager):
    """Test exporting config as raw dictionary."""
    section_data = {"key1": "value1", "key2": "value2"}

    await config_manager.set_config("export_raw_section", value=section_data)

    exported_config = await config_manager.export_config("export_raw_section", raw=True)

    assert isinstance(exported_config, dict), "Expected raw dictionary export"
    assert exported_config == section_data, "Expected correct dictionary data"


@pytest.mark.asyncio
async def test_export_full_section_json(config_manager):
    """Test exporting a full section in JSON format."""
    section, section_data = "export_section", {"key1": "value1", "key2": "value2"}

    # Set section
    await config_manager.set_config(section, value=section_data)

    # Export and validate JSON format
    json_export = await config_manager.export_config(section, fmt="json")
    assert isinstance(json_export, str), "Expected JSON export to be a string"
    assert (
        json.loads(json_export) == section_data
    ), f"Expected {section_data}, got {json.loads(json_export)}"


@pytest.mark.asyncio
async def test_export_full_section_yaml(config_manager):
    """Test exporting a full section in YAML format."""
    section, section_data = "export_section_yaml", {"key1": "value1", "key2": "value2"}

    # Set section
    await config_manager.set_config(section, value=section_data)

    # Export and validate YAML format
    yaml_export = await config_manager.export_config(section, fmt="yaml")
    assert isinstance(yaml_export, str), "Expected YAML export to be a string"
    assert (
        yaml.safe_load(yaml_export) == section_data
    ), f"Expected {section_data}, got {yaml.safe_load(yaml_export)}"


@pytest.mark.asyncio
async def test_export_full_section_toml(config_manager):
    """Test exporting a full section in TOML format."""
    section, section_data = "export_section_toml", {"key1": "value1", "key2": "value2"}

    # Set section
    await config_manager.set_config(section, value=section_data)

    # Export and validate TOML format
    toml_export = await config_manager.export_config(section, fmt="toml")
    assert isinstance(toml_export, str), "Expected TOML export to be a string"
    assert (
        toml.loads(toml_export) == section_data
    ), f"Expected {section_data}, got {toml.loads(toml_export)}"


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


@pytest.mark.asyncio
async def test_export_config(config_manager):
    """Test exporting configuration data in different formats."""

    section, key, value = "export_section1", "key1", "exported_value"

    # Step 1: Set initial config
    await config_manager.set_config(section, key, value)
    # Fix: Ensure expected output matches the corrected TOML behavior
    expected_toml = '[config_value]\nconfig_value = "exported_value"\n'

    # Step 2: Test JSON export
    json_export = await config_manager.export_config(section, key, fmt="json")
    assert isinstance(json_export, str), "JSON export should return a string"
    assert (
        json.loads(json_export) == value
    ), f"Expected '{value}', got '{json.loads(json_export)}'"

    # Step 3: Test YAML export
    yaml_export = await config_manager.export_config(section, key, fmt="yaml")
    assert isinstance(yaml_export, str), "YAML export should return a string"
    assert (
        yaml.safe_load(yaml_export) == value
    ), f"Expected '{value}', got '{yaml.safe_load(yaml_export)}'"

    # Test TOML export (Fix expected output)
    toml_export = await config_manager.export_config(section, key, fmt="toml")
    assert (
        toml_export.strip() == expected_toml.strip()
    ), f"Expected:\n{expected_toml}\nGot:\n{toml_export}"

    # # Step 4: Test TOML export
    # toml_export = await config_manager.export_config(section, key, format="toml")
    # assert isinstance(toml_export, str), "TOML export should return a string"
    # assert toml.loads(toml_export) == {"value": value}, f"Expected '{{value: {value}}}', got '{toml.loads(toml_export)}'"

    # Step 5: Test exporting a non-existent key (should return empty string)
    empty_export = await config_manager.export_config(
        "non_existent_section", "non_existent_key", fmt="json"
    )
    assert empty_export == "", "Expected an empty string for non-existent config"

    # Step 6: Test export as bytes (for binary support)
    json_export_bytes = await config_manager.export_config(
        section, key, fmt="json", as_bytes=True
    )
    assert isinstance(
        json_export_bytes, bytes
    ), "Expected bytes output when as_bytes=True"
    assert (
        json.loads(json_export_bytes.decode()) == value
    ), "Decoded JSON should match expected value"

    # Step 7: Test invalid format handling
    with pytest.raises(
        ValueError, match="Unsupported format. Choose 'json', 'yaml', or 'toml'."
    ):
        await config_manager.export_config(section, key, fmt="invalid_format")


@pytest.mark.asyncio
async def test_export_config_raw(config_manager):
    """Ensure exporting configuration as raw data works correctly."""

    # Step 1: Set test configurations
    test_configs = {
        "export_section1": {"key1": "value1", "key2": 42},
        "export_section2": {"key_a": True, "key_b": [1, 2, 3]},
    }
    await config_manager.set_bulk_config(test_configs)

    # Step 2: Export raw config
    exported_config = await config_manager.export_config(raw=True)

    # Step 3: Verify exported structure
    assert isinstance(exported_config, dict), "Exported config should be a dictionary"
    assert "export_section1" in exported_config, "Missing 'export_section1'"
    assert "export_section2" in exported_config, "Missing 'export_section2'"
    assert (
        exported_config["export_section1"]["key1"] == "value1"
    ), "Incorrect value for key1"

    await flush_redis_cache(config_manager)
