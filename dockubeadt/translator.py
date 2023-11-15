import os
import re
import subprocess
import sys
from tempfile import NamedTemporaryFile
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML

from . import __version__

yaml = YAML()

WORKLOADS = ["deployment", "pod", "statefulset", "daemonset"]

def translate(file, stream=False):
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
    """Check whether the given dictionary is a Docker Compose
    """
    return "services" in list(yaml.load_all(data))[0]


def validate_compose(compose):
    """Check whether the given Docker Compose file contains more than one containers

    Args:
        dicts (dictionary): Dictionary containing Docker Compose contents

    Returns:
        string: name of the container
    """
    services = compose["services"]
    if len(services) > 1:
        raise ValueError("DocKubeADT does not support conversion of multiple containers")
    return list(services.keys())[0]

def check_bind_propagation(container):
    """Check whether a container has volume bind propagation

    Args:
        dicts (dictionary): Dictionary containing the container details

    Returns:
        volume_data: details regarding the bind propagation
    """
    volume_data = []
    for volume in container.get("volumes", []):
        volume_data.append(get_propagation(volume))

    return volume_data

def get_propagation(volume):
    mapping = {
        "rshared": "Bidirectional",
        "rslave": "HostToContainer"
    }
    try:
        return mapping[volume["bind"]["propagation"]]
    except (KeyError, TypeError):
        return None


def run_command(cmd):
    """Run a command, getting RC and output"""

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
    """Check whether the given file Docker Compose contains more than one containers

    Args:
        dicts (dictionary): Dictionary containing Docker Compose file

    Returns:
        dict: Kubernetes manifests
    """
    out_file = f"{container_name}.yaml"
    with NamedTemporaryFile("w", dir=os.getcwd()) as tmpfile:
        yaml.dump(dicts, tmpfile)
        cmd = f"""
            kompose convert \
            -f {tmpfile.name} \
            --volumes hostPath \
            --out {out_file}
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


def translate_manifest(manifests, propagation: list = None, configuration_data: list = None):
    """Translates K8s Manifest(s) to a MiCADO ADT

    Args:
        file (string): Path to Kubernetes manifest
    Returns:
        adt: ADT in dictionary format
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
    return len(
        [
            manifest for manifest
            in manifests
            if manifest and manifest["kind"].lower() in WORKLOADS
        ]
    )

def _add_configdata(configuration_data, node_templates):
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
    """Transforms a single manifest into a node template

    Args:
        manifests (iter): Iterable of k8s manifests
        filename (string): Name of the file
        node_templates (dict): `node_templates` key of the ADT
    """

    for manifest in manifests:

        name = manifest["metadata"]["name"].lower()
        kind = manifest["kind"].lower()
        node_name = f"{name}-{kind}"

        if kind not in WORKLOADS:
            node_templates[node_name] = _to_node(manifest)
            continue

        container = get_container_from_manifest(manifest)
        if not container:
            continue
        
        _update_propagation(container, propagation)


        for conf in configuration_data:
            spec = manifest["spec"]
            if "mount_propagation" in conf:
            # Handle AMR snake_case naming
                conf["mountPropagation"] = conf.pop("mount_propagation")
            if spec.get("containers") is None:
                new_spec = spec["template"]["spec"]
                _add_volume(new_spec, conf)
            else:
                _add_volume(spec, conf)

        node_templates[node_name] = _to_node(manifest)

def get_container_from_manifest(manifest):
    spec = manifest.get("spec")
    if not spec:
        return None

    if "containers" not in spec:
        spec = spec["template"]["spec"]

    try:
        container = spec["containers"][0]
    except (IndexError, KeyError):
        return None

    return container

def _update_propagation(container, propagation):
    vol_mounts = container.get("volumeMounts", [])
    for prop, mount in zip(propagation, vol_mounts):
        if not prop:
            continue
        mount["mountPropagation"] = prop

def _add_volume(spec, conf):
    containers = spec["containers"]
    for container in containers:
        volume_mounts = container.setdefault("volumeMounts", [])

        # Using subPath here to always mount files individually.
        # (DIGITbrain configuration files are always single file ConfigMaps.)
        file = conf["file_path"]
        in_path = Path(file)
        cfg_name = in_path.name.lower().replace(".", "-").replace("_", "-").replace(" ", "-")
        filename = os.path.basename(file)
        volume_mount = {"name": cfg_name, "mountPath": file, "subPath": filename}
        if (conf.get("mountPropagation") is not None) and (
            conf.get("mountPropagation")
        ):
            volume_mount["mountPropagation"] = conf["mountPropagation"]

        volume_mounts.append(volume_mount)

    volumes = spec.setdefault("volumes", [])
    volumes.append({"name": cfg_name, "configMap": {"name": cfg_name}})


def _get_default_adt():
    """Returns the boilerplate for a MiCADO ADT

    Args:
        filename (string): Filename of K8s manifest(s)

    Returns:
        dict: ADT boilerplate
    """
    return {
        "node_templates": {},
    }


def _to_node(manifest):
    """Inlines the Kubernetes manifest under node_templates

    Args:
        manifest (dict): K8s manifest

    Returns:
        dict: ADT node_template
    """
    metadata = manifest["metadata"]
    metadata.pop("annotations", None)
    metadata.pop("creationTimestamp", None)
    manifest["metadata"] = metadata

    if manifest.get("spec") is not None:
        spec = manifest["spec"]
        if spec.get("template") is not None:
            template = spec["template"]
            if template.get("metadata") is not None:
                template_metadata = template["metadata"]
                template_metadata.pop("annotations", None)
                template_metadata.pop("creationTimestamp", None)
                manifest["spec"]["template"]["metadata"] = template_metadata

    manifest.pop("status", None)
    return {
        "type": "tosca.nodes.MiCADO.Kubernetes",
        "interfaces": {"Kubernetes": {"create": {"inputs": manifest}}},
    }
