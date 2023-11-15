import os
import re
from pathlib import Path

WORKLOADS = ["deployment", "pod", "statefulset", "daemonset"]


def count_workloads(manifests):
    """
    Counts the number of workloads in the given list of manifests.

    Args:
        manifests (list): A list of Kubernetes manifests.

    Returns:
        int: The number of workloads in the given list of manifests.
    """
    return len(
        [
            manifest
            for manifest in manifests
            if manifest and manifest["kind"].lower() in WORKLOADS
        ]
    )


def get_spec_and_container(manifest):
    """
    Given a Kubernetes manifest, returns the spec and first container definition
    found in the manifest's spec. If no container is found, returns None.

    Args:
        manifest (dict): A Kubernetes manifest.

    Returns:
        tuple: A tuple containing the spec and container definition, or None if no
        container is found.
    """
    spec = manifest.get("spec")
    if not spec:
        return None

    if "containers" not in spec:
        spec = spec["template"]["spec"]

    try:
        container = spec["containers"][0]
    except (IndexError, KeyError):
        return None

    return spec, container


def add_configdata(configuration_data, node_templates):
    """
    Add configuration data to the ADT.

    Args:
        configuration_data (list): A list of dictionaries containing configuration data.
        node_templates (dict): A dictionary containing the ADT.

    Returns:
        None
    """
    for conf in configuration_data:
        file_name = Path(conf["file_path"]).name
        file_content = conf["file_content"]

        # Handle incoming Windows-style newlines
        file_content = re.sub(r'\r\s*\n', '\n', file_content)
        
        configmap = {
            "type": "tosca.nodes.MiCADO.Container.Config.Kubernetes",
            "properties": {"data": {file_name: file_content}},
        }

        node_name = (
            file_name.lower().replace(".", "-").replace("_", "-").replace(" ", "-")
        )
        node_templates[node_name] = configmap


def update_propagation(container, propagation):
    """
    Update the mount propagation for each volume mount in the container.

    Args:
        container (dict): The container to update.
        propagation (list): A list of mount propagation values to apply to each
            volume mount in the container.

    Returns:
        None
    """
    vol_mounts = container.get("volumeMounts", [])
    for prop, mount in zip(propagation, vol_mounts):
        if not prop:
            continue
        mount["mountPropagation"] = prop


def update_configmaps(spec, container, configuration_data):
    """
    Update the Kubernetes spec and container with the configuration data.

    Args:
        spec (dict): The Kubernetes spec to update.
        container (dict): The container to update.
        configuration_data (list): A list of configuration data.

    Returns:
        None
    """
    volumes = spec.setdefault("volumes", [])
    volume_mounts = container.setdefault("volumeMounts", [])
    for configmap in configuration_data:
        # Using subPath here to always mount files individually.
        # (DIGITbrain configuration files are always single file ConfigMaps.)
        file = configmap["file_path"]
        cfg_name = (
            Path(file)
            .name.lower()
            .replace(".", "-")
            .replace("_", "-")
            .replace(" ", "-")
        )
        volumes.append({"name": cfg_name, "configMap": {"name": cfg_name}})

        filename = os.path.basename(file)
        volume_mount = {"name": cfg_name, "mountPath": file, "subPath": filename}
        volume_mounts.append(volume_mount)
