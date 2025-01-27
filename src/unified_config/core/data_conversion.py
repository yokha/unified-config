from typing import Any, Union
import json
import yaml
import toml


def load_config_file(file_path: str) -> Union[dict, list]:
    """
    Load a configuration file, automatically detecting its format (JSON, YAML, TOML).

    Args:
        file_path (str): Path to the configuration file.

    Returns:
        Union[dict, list]: Parsed configuration data.

    Raises:
        ValueError: If the file format is unsupported.
    """
    with open(file_path, "r") as file:
        if file_path.endswith((".json", ".JSON")):
            return json.load(file)
        if file_path.endswith((".yaml", ".yml", ".YAML", ".YML")):
            return yaml.safe_load(file)
        if file_path.endswith((".toml", ".TOML")):
            return toml.load(file)

        raise ValueError("Unsupported config file format. Use JSON, YAML, or TOML.")


def save_config_file(file_path: str, data: Union[dict, list]) -> None:
    """
    Save configuration data to a file, automatically determining the format.

    Args:
        file_path (str): Path where the config should be saved.
        data (Union[dict, list]): The config data to save.

    Raises:
        ValueError: If the file format is unsupported.
    """
    with open(file_path, "w") as file:
        if file_path.endswith((".json", ".JSON")):
            json.dump(data, file, indent=4)
        elif file_path.endswith((".yaml", ".yml", ".YAML", ".YML")):
            yaml.safe_dump(data, file, default_flow_style=False)
        elif file_path.endswith((".toml", ".TOML")):
            toml.dump(data, file)
        else:
            raise ValueError("Unsupported config file format. Use JSON, YAML, or TOML.")


def convert_config(data: Any, fmt: str) -> str:
    """
    Convert a dictionary/list to a formatted string in JSON, YAML, or TOML.

    Args:
        data (Any): The configuration data.
        format (str): Desired format ("json", "yaml", "toml").

    Returns:
        str: The formatted string.

    Raises:
        ValueError: If the format is unsupported.
    """
    if fmt == "json":
        return json.dumps(data, indent=4)

    if fmt == "yaml":
        return yaml.safe_dump(data, default_flow_style=False)

    if fmt == "toml":
        if isinstance(data, dict):
            return toml.dumps(data).strip() + "\n"
        if isinstance(data, list):
            # Ensure list is formatted in a multi-line TOML array
            formatted_list = ",\n    ".join(f'"{item}"' for item in data)
            return f"[config_list]\nconfig_list = [\n    {formatted_list}\n]\n"

        if isinstance(data, str):
            # Ensure string is stored under `[config_value]`
            return f'[config_value]\nconfig_value = "{data}"\n'

        raise ValueError("TOML format requires a dictionary, list, or string.")
    raise ValueError("Unsupported format. Choose 'json', 'yaml', or 'toml'.")
