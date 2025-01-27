import pytest
from pydantic import ValidationError
from unified_config.core.schemas import ConfigValue, ConfigEntry, ConfigSection


### 🔹 TESTS FOR ConfigValue ###
@pytest.mark.parametrize(
    "valid_value",
    [
        "string_value",
        123,
        45.67,
        True,
        {"key": "value"},
        ["item1", "item2"],
    ],
)
def test_config_value_valid(valid_value):
    """Test valid values for ConfigValue"""
    config = ConfigValue(value=valid_value)

    assert config.value == valid_value


@pytest.mark.parametrize(
    "invalid_value",
    [
        set(["invalid"]),  # Sets are not JSON serializable
        object(),  # Generic object instance
    ],
)
def test_config_value_invalid(invalid_value):
    """Test invalid values for ConfigValue"""
    with pytest.raises(ValidationError):
        ConfigValue(value=invalid_value)


### 🔹 TESTS FOR ConfigEntry ###
def test_config_entry_valid():
    """Test a valid ConfigEntry"""
    entry = ConfigEntry(
        section="database", key="host", value=ConfigValue(value="localhost")
    )
    assert entry.section == "database"
    assert entry.key == "host"
    assert entry.value.value == "localhost"


@pytest.mark.parametrize(
    "invalid_section, invalid_key",
    [
        ("", "valid_key"),  # Empty section
        ("valid_section", ""),  # Empty key
        ("", ""),  # Both empty
    ],
)
def test_config_entry_invalid(invalid_section, invalid_key):
    """Test invalid ConfigEntry with empty fields"""
    with pytest.raises(ValidationError):
        ConfigEntry(
            section=invalid_section,
            key=invalid_key,
            value=ConfigValue(value="localhost"),
        )


### 🔹 TESTS FOR ConfigSection ###
def test_config_section_valid_dict():
    """Test ConfigSection with a dictionary of values"""
    section = ConfigSection(
        section="app_settings", values={"theme": "dark", "notifications": True}
    )
    assert section.section == "app_settings"
    assert section.values["theme"] == "dark"
    assert section.values["notifications"] is True


def test_config_section_valid_list():
    """Test ConfigSection with a list of values"""
    section = ConfigSection(section="allowed_ips", values=["192.168.1.1", "10.0.0.2"])
    assert section.section == "allowed_ips"
    assert section.values == ["192.168.1.1", "10.0.0.2"]


@pytest.mark.parametrize(
    "invalid_values",
    [
        None,  # `None` is still not allowed
    ],
)
def test_config_section_invalid(invalid_values):
    """Test ConfigSection rejects None values."""
    with pytest.raises(ValidationError) as exc_info:
        ConfigSection(section="invalid_section", values=invalid_values)

    # Use substring matching to avoid exact regex issues
    assert (
        "Configuration section must be a dictionary, list, or a primitive value"
        in str(exc_info.value)
    )


@pytest.mark.parametrize(
    "valid_values",
    [
        "string_value",  # Now allowed
        123,  # Now allowed
        3.14,  # Now allowed
        True,  # Now allowed
        {"key": "value"},  # Dictionary (still valid)
        ["item1", "item2"],  # List (still valid)
    ],
)
def test_config_section_valid(valid_values):
    """Ensure ConfigSection correctly accepts valid types."""
    try:
        config = ConfigSection(section="valid_section", values=valid_values)
        assert config.values == valid_values, f"Unexpected value: {config.values}"
    except ValidationError:
        pytest.fail(f"ValidationError raised for valid value: {valid_values}")
