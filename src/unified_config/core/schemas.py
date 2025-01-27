import re
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Union, Dict, List
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    ValidationInfo,
)


class ConfigValue(BaseModel):
    """
    Represents a single config value, which can be a string, number, boolean, dictionary, or list.
    """

    value: Union[str, int, float, bool, dict, list]

    @field_validator("value", mode="before")
    @classmethod
    def ensure_valid_value(cls, v):
        """Ensure value is valid: disallow None at the top level but allow inside dicts."""
        if v is None:
            raise ValueError(
                "Configuration value cannot be None. Use an empty string or a placeholder instead."
            )

        if isinstance(v, set):
            raise ValueError("Sets are not allowed in configuration values.")

        try:
            json.dumps(v)  # Ensure serializability
        except (TypeError, ValueError) as exc:
            raise ValueError("Configuration value must be JSON serializable.") from exc

        return v


class ConfigEntry(BaseModel):
    """
    Represents a configuration entry consisting of:

    - `section` (str): A non-empty section name, restricted to lowercase letters, numbers, underscores, or hyphens.
    - `key` (str): A non-empty key name, following the same naming rules as `section`.
    - `value` (ConfigValue): The actual configuration value, which can be a string, number, boolean, dictionary, or list.

    The `value` field is automatically wrapped into a `ConfigValue` instance if a raw value is provided.
    """

    section: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1)
    value: ConfigValue  # Ensures value is always a ConfigValue instance

    @field_validator("value", mode="before")
    @classmethod
    def wrap_in_config_value(cls, v):
        """
        Ensure that the value is wrapped inside a `ConfigValue` instance.

        - If `v` is already a `ConfigValue`, return it unchanged.
        - Otherwise, wrap the raw value inside a `ConfigValue` instance.

        Args:
            v (Any): The input value to validate.

        Returns:
            ConfigValue: The validated and wrapped configuration value.
        """
        if isinstance(v, ConfigValue):
            return v
        return ConfigValue(value=v)  # Automatically wrap raw values

    @field_validator("section", "key", mode="before")
    @classmethod
    def validate_format(cls, v, info: ValidationInfo):
        """
        Enforce formatting rules for `section` and `key` fields.

        - Fields cannot be empty.
        - Only lowercase letters, numbers, underscores, and hyphens are allowed.

        Args:
            v (str): The input string value for validation.
            info (ValidationInfo): Metadata about the field being validated.

        Returns:
            str: The validated and formatted string.

        Raises:
            ValueError: If the value is empty or does not match the required format.
        """
        field_name = info.field_name  # Correct way to get field name in Pydantic 2.0+

        if not v:
            raise ValueError(f"{field_name} cannot be empty.")

        if not re.match(r"^[a-z0-9_-]+$", v):
            raise ValueError(
                f"{field_name} must be lowercase and contain only letters, numbers, underscores, or hyphens."
            )

        return v


class ConfigSection(BaseModel):
    """
    Represents a configuration section, which can contain:
    - A dictionary of key-value pairs.
    - A list of ordered values.
    - A single primitive value (str, int, float, bool, None).
    """

    section: str = Field(..., min_length=1)
    values: Union[Dict[str, Any], List[Any], str, int, float, bool]

    @field_validator("values", mode="before")
    @classmethod
    def ensure_valid_structure(cls, v):
        """
        Allow `values` to be a dictionary, a list, or a single primitive value.

        Args:
            v (Any): The input value for validation.

        Returns:
            Union[Dict[str, Any], List[Any], str, int, float, bool, None]: The validated `values` field.
        """
        if not isinstance(v, (dict, list, str, int, float, bool)):
            raise ValueError(
                "Configuration section must be a dictionary, list, or a primitive value (str, int, float, bool)."
            )
        return v


class ConfigHistory(BaseModel):
    """
    Represents a configuration change history record.
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the config history entry.",
    )
    section: str = Field(..., description="The section of the configuration.")
    key: Union[str, None] = Field(
        None, description="The specific key in the configuration section."
    )
    new_value: Union[str, int, float, bool, dict, list, None] = Field(
        None,
        description="The new value after modification. None indicates a deletion or unset value.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="The time when the change was made.",
    )
    updated_by: str = Field(
        ..., description="User or system responsible for the change."
    )

    @classmethod
    def from_orm(cls, obj):
        """Convert ORM model instance to Pydantic model."""
        return cls(
            id=str(obj.id),
            section=obj.section,
            key=obj.key,
            new_value=obj.new_value,
            timestamp=obj.timestamp,
            updated_by=obj.updated_by,
        )
