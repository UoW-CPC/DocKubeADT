from dockubeadt.utils import load_multi_yaml


def is_compose(data):
    """
    Check if the given data is a Docker Compose file by
    looking for the 'services' key.

    Args:
        data (str): The YAML data to check.

    Returns:
        bool: True if the data is a Docker Compose file, False otherwise.
    """
    return "services" in load_multi_yaml(data)[0]


def get_container_and_name(compose):
    """
    Gets the container from the Docker Compose file. Raises an error if
    the file contains more than one container.

    Args:
        compose (dict): A dictionary representing the Docker Compose file.

    Returns:
        str: The name of the service to be converted.

    Raises:
        ValueError: If the Docker Compose file contains more than one service.
    """
    services = compose["services"]
    if len(services) > 1:
        raise ValueError(
            "DocKubeADT does not support multiple containers"
        )
    container_name = list(services.keys())[0]
    container = services[container_name]
    return container, container_name


def check_bind_propagation(container):
    """
    Check the propagation of bind mounts for a given container.

    Args:
        container (dict): A dictionary representing the container.

    Returns:
        list: A list of propagation data for each volume in the container.
    """
    volume_data = []
    for volume in container.get("volumes", []):
        volume_data.append(_get_propagation(volume))

    return volume_data


def fix_open_param_volumes(container):
    """
    Fixes the volumes in the given container by prepending a forward
    slash to the target and source paths if they start as open_parameters.

    Args:
        container (dict): A dictionary representing the container.

    Returns:
        None
    """
    for i, vol in enumerate(container.get("volumes", [])):
        if isinstance(vol, dict):
            vol["target"] = _fix_if_open_param(vol["target"])
            vol["source"] = _fix_if_open_param(vol["source"])

        elif isinstance(vol, str):
            target, source = vol.split(":")[:2]
            container["volumes"][
                i
            ] = f"{_fix_if_open_param(target)}:{_fix_if_open_param(source)}"


def _get_propagation(volume):
    """
    Returns the propagation mode for the given volume.

    Args:
        volume (dict): A dictionary representing the volume.

    Returns:
        str: The propagation mode for the volume, or None if it cannot be determined.
    """
    mapping = {"rshared": "Bidirectional", "rslave": "HostToContainer"}
    try:
        return mapping[volume["bind"]["propagation"]]
    except (KeyError, TypeError):
        return None


def _fix_if_open_param(path):
    """
    Prepends a forward slash to the path if it starts with the match pattern.

    Args:
        path (str): The path to check and modify.
        match_pattern (str): The pattern to check for at the start of the path.

    Returns:
        str: The modified path.
    """
    MATCH = "open_parameter{"
    if path.startswith(MATCH):
        return f"/{path}"
    return path
