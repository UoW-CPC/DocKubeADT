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
