import os
import re
import subprocess
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from ruamel.yaml import YAML

from dockubeadt import __version__

yaml = YAML()

WORKLOADS = ["deployment", "pod", "statefulset", "daemonset"]

def translate(file, stream=False):
    """
    Translates a Docker Compose file or a Kubernetes manifest file into an ADT.

    Args:
        file (str): The path to the file to be translated, or the file contents if `stream` is True.
        stream (bool, optional): Whether `file` contains the file contents directly. Defaults to False.

    Returns:
        dict: A dictionary representing the ADT.
    """

    if not stream:
        with open(file, "r") as in_file:
            data = in_file.read()
    else:
        data = file

    if is_compose(data):
        composes = yaml.load(data)
        mdt = translate_dict("docker-compose", composes)

    else:
        manifests = yaml.load_all(data)
        mdt = translate_dict("kubernetes-manifest", manifests)

    mdt = yaml.load(mdt)
    return {"topology_template": mdt}


def translate_dict(
    deployment_format,
    topology_metadata,
    configuration_data: list = None,
):
    """
    Translates the metadata from the specified deployment format.

    Args:
        deployment_format (str): The deployment format to translate to.
          Must be either 'docker-compose' or 'kubernetes-manifest'.

        topology_metadata (dict): The topology metadata to translate.
        
        configuration_data (list, optional): The configuration data to use
          for the translation. Defaults to None.

    Raises:
        ValueError: If the deployment_format is not 'docker-compose' or 'kubernetes-manifest'.

    Returns:
        str: The translated topology metadata in YAML format.
    """
    print(f"Running DocKubeADT v{__version__}")
    
    if deployment_format not in ["docker-compose", "kubernetes-manifest"]:
        raise ValueError(
            "Unsupported deployment_format. Expected 'docker-compose' or 'kubernetes-manifest'"
        )
    
    configuration_data = configuration_data or []
    propagation = []

    if deployment_format == "docker-compose":
        container_name = get_container_from_compose(topology_metadata)
        container = topology_metadata["services"][container_name]
        propagation = check_bind_propagation(container)
        topology_metadata = convert_doc_to_kube(topology_metadata, container_name)
    
    mdt = translate_manifest(topology_metadata, propagation, configuration_data)

    buffer = StringIO()
    yaml.dump(mdt, buffer)

    print("Translation completed successfully")

    return buffer.getvalue()


def is_compose(data):
    """
    Check if the given data is a Docker Compose file by
    looking for the 'services' key.

    Args:
        data (str): The YAML data to check.

    Returns:
        bool: True if the data is a Docker Compose file, False otherwise.
    """
    return "services" in list(yaml.load_all(data))[0]


def get_container_from_compose(compose):
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
        raise ValueError("DocKubeADT does not support conversion of multiple containers")
    return list(services.keys())[0]

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
        volume_data.append(get_propagation(volume))

    return volume_data

def get_propagation(volume):
    """
    Returns the propagation mode for the given volume.

    Args:
        volume (dict): A dictionary representing the volume.

    Returns:
        str: The propagation mode for the volume, or None if it cannot be determined.
    """
    mapping = {
        "rshared": "Bidirectional",
        "rslave": "HostToContainer"
    }
    try:
        return mapping[volume["bind"]["propagation"]]
    except (KeyError, TypeError):
        return None

def run_command(cmd):
    """
    Executes a shell command and returns the output and return code.

    Args:
        cmd (str): The command to execute.

    Returns:
        tuple: A tuple containing the return code and output of the command.
    """
    with subprocess.Popen(
            cmd, 
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            shell=True
    ) as p:
        
        output = ""
        for line in p.stdout:
            # Regex gets rid of additional characters in Kompose output
            output += re.sub(
                r'\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))',
                '',
                line.decode()
            )
    return p.returncode, output

def convert_doc_to_kube(dicts, container_name):
    """
    Converts a Docker Compose file to Kubernetes manifests using Kompose.

    Args:
        dicts (dict): A dictionary containing the Docker Compose file contents.
        container_name (str): The name of the container.

    Returns:
        generator: A generator object containing the Kubernetes manifests.
    """
    
    out_file = f"{container_name}.yaml"
    with NamedTemporaryFile("w", dir=os.getcwd()) as tmpfile:
        yaml.dump(dicts, tmpfile)
        cmd = f"""
            kompose convert \
            -f {tmpfile.name} \
            --volumes hostPath \
            --out {out_file} \
            --with-kompose-annotation=false
        """
        status, stdout = run_command(cmd)

    print(stdout)

    if status != 0:
        raise ValueError(f"Docker Compose has a validation error")
    
    with open(out_file, "r") as f:
        manifests = yaml.load_all(f.read())
    os.remove(out_file)
    print(f'INFO Kubernetes file "{out_file}" removed')

    return manifests


def translate_manifest(
        manifests,
        propagation: list = None,
        configuration_data: list = None
    ):
    """
    Translates a Kubernetes manifest file into an Azure Deployment Template (ADT).

    Args:
        manifests (list): A list of Kubernetes manifest files.
        propagation (list, optional): A list of Kubernetes propagation policies. Defaults to None.
        configuration_data (list, optional): A list of configuration data. Defaults to None.

    Returns:
        dict: An Azure Deployment Template (ADT) object.
    """
    manifests = list(manifests)
    if count_workloads(manifests) > 1:
        raise ValueError("Manifest file cannot have more than one workload.")

    adt = _get_default_adt()
    node_templates = adt["node_templates"]
    if configuration_data is not None:
        _add_configdata(configuration_data, node_templates)
    _transform(manifests, node_templates, propagation, configuration_data)
    return adt

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
            manifest for manifest
            in manifests
            if manifest and manifest["kind"].lower() in WORKLOADS
        ]
    )

def _add_configdata(configuration_data, node_templates):
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
        configmap = {
            "type": "tosca.nodes.MiCADO.Container.Config.Kubernetes",
            "properties": {
                "data": {file_name: file_content}
            }
        }

        node_name = file_name.lower().replace(".", "-").replace("_", "-").replace(" ", "-")
        node_templates[node_name] = configmap


def _transform(
    manifests, node_templates, propagation: list = None, configuration_data: list = None
):
    """
    Transforms Kubernetes manifests into node templates for use in a Docker Compose file.

    Args:
        manifests (list): A list of Kubernetes manifests.
        node_templates (dict): A dictionary of node templates to be populated.
        propagation (list, optional): A list of propagation options. Defaults to None.
        configuration_data (list, optional): A list of configuration data. Defaults to None.
    """
    for manifest in manifests:

        name = manifest["metadata"]["name"].lower()
        kind = manifest["kind"].lower()
        node_name = f"{name}-{kind}"

        if kind not in WORKLOADS:
            node_templates[node_name] = _to_node(manifest)
            continue

        spec, container = get_spec_container_from_manifest(manifest)
        if not container:
            continue

        _update_propagation(container, propagation)
        _update_configmaps(spec, container, configuration_data)

        node_templates[node_name] = _to_node(manifest)

def get_spec_container_from_manifest(manifest):
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

def _update_propagation(container, propagation):
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

def _update_configmaps(spec, container, configuration_data):
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
        cfg_name = Path(file).name.lower().replace(".", "-").replace("_", "-").replace(" ", "-")
        volumes.append({"name": cfg_name, "configMap": {"name": cfg_name}})

        filename = os.path.basename(file)
        volume_mount = {"name": cfg_name, "mountPath": file, "subPath": filename}
        volume_mounts.append(volume_mount)

def _get_default_adt():
    """Returns the boilerplate for a MiCADO ADT

    Returns:
        dict: ADT boilerplate
    """
    return {
        "node_templates": {},
    }


def _to_node(manifest):
    """Inlines the Kubernetes manifest under a node template

    Args:
        manifest (dict): K8s manifest

    Returns:
        dict: ADT node_template
    """

    return {
        "type": "tosca.nodes.MiCADO.Kubernetes",
        "interfaces": {"Kubernetes": {"create": {"inputs": manifest}}},
    }
