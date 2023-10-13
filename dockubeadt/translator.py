import os
import re
import subprocess
import sys
from io import StringIO
from pathlib import Path

import ruamel.yaml as yaml

from . import __version__

INVOKED_AS_LIB=False

def translate(file, stream=False):
    if not stream:
        with open(file, "r") as in_file:
            data = in_file.read()
    else:
        data = file

    dicts = yaml.safe_load_all(data)
    type = check_type(dicts)

    if type == "kubernetes-manifest":
        manifests = yaml.safe_load_all(data)
        mdt = translate_dict(type, manifests)
    elif type == "docker-compose":
        composes = yaml.safe_load(data)
        mdt = translate_dict(type, composes)

    adt = "topology_template:\n" + mdt
    return adt


def translate_dict(
    deployment_format,
    topology_metadata,
    configurationData: list = None,
):
    print(f"Running DocKubeADT v{__version__}")
    global INVOKED_AS_LIB
    INVOKED_AS_LIB=True
    configurationData = configurationData if configurationData else []
    volumeData = []
    portData = []
    if deployment_format == "kubernetes-manifest":
        mdt = translate_manifest(topology_metadata, volumeData, portData, configurationData)
    elif deployment_format == "docker-compose":
        container_name = validate_compose(topology_metadata)
        container = topology_metadata["services"][container_name]
        volumeData = check_bind_propagation(container)
        portData = check_long_syntax_port(container)
        convert_doc_to_kube(topology_metadata, container_name)
        file_name = "{}.yaml".format(container_name)
        with open(file_name, "r") as f:
            data_new = f.read()
        manifests = yaml.safe_load_all(data_new)
        mdt = translate_manifest(manifests, volumeData, portData, configurationData)
        cmd = "rm {}*".format(container_name)
        run_command(cmd)
    else:
        raise ValueError(
            "The deploymentFormat should be either 'docker-compose' or 'kubernetes-manifest'"
        )

    _yaml = yaml.YAML()
    _yaml.preserve_quotes = True
    _yaml.width = 800
    dt_stream = StringIO()
    _yaml.dump(mdt, dt_stream)
    adt_str = dt_stream.getvalue()
    adt = ""
    for line in adt_str.splitlines():
        adt = adt + "  " + line + "\n"
    adt = adt[: adt.rfind("\n")]
    print("Translation completed successfully")

    return adt


def check_type(dicts):
    """Check whether the given dictionary is a Docker Compose or K8s Manifest

    Args:
        dicts (dictionary): dictionary containing a docker compose or k8s manifest

    Returns:
        string: docker-compose or kubernetes-manifest
    """
    dict = list(dicts)[0]
    if "kind" in dict:
        type = "kubernetes-manifest"
    elif "services" in dict:
        type = "docker-compose"
    return type


def validate_compose(dicts):
    """Check whether the given Docker Compose file contains more than one containers

    Args:
        dicts (dictionary): Dictionary containing Docker Compose contents

    Returns:
        string: name of the container
    """
    dict = dicts["services"]
    if len(dict) > 1:
        print(
            "Docker compose file can't have more than one containers. Exiting..."
        )
        raise ValueError("Docker compose file has more than one container")
    name = next(iter(dict))
    return name

def check_bind_propagation(container):
    """Check whether a container has volume bind propagation

    Args:
        dicts (dictionary): Dictionary containing the container details

    Returns:
        volume_data: details regarding the bind propagation
    """
    volumes = container.get("volumes")
    volume_data = []
    i = 0
    if volumes is not None:
        for volume in volumes:
            if (type(volume) is dict):
                if (volume.get("bind") is not None):
                    propagation = volume["bind"]["propagation"]
                    target = volume['target']
                    if propagation == "rshared":
                        mountPropagation = "Bidirectional"
                    if propagation == "rslave":
                        mountPropagation = "HostToContainer"
                    volume_data.append({"id":i, "mountPath":target, "mountPropagation":mountPropagation})
            i = i+1

    return volume_data

def check_long_syntax_port(container):
    """Check whether a container has a long syntax for port binding

    Args:
        dicts (dictionary): Dictionary containing the container details

    Returns:
        port_data: details of port mapping to add the hostPort in manifest
    """
    ports = container.get("ports")
    port_data = []
    i = 0
    if ports is not None:
        for port in ports:
            if (type(port) is dict):
                long_syntax = port
                short_syntax = f"{long_syntax['published']}:{long_syntax['target']}{'/udp' if long_syntax.get('protocol') == 'udp' else ''}"
                ports[i] = short_syntax
                if long_syntax.get("mode") == "host":
                    port_data.append({"id":i, "containerport":int(long_syntax['target']), "hostport":int(long_syntax['published'])})
            i = i+1
    return port_data

def run_command(cmd):
    global INVOKED_AS_LIB
    if INVOKED_AS_LIB:
        sys.stdout.flush()
        with subprocess.Popen(cmd, 
                stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True) as p:
            for line in p.stdout:
                print(re.sub(r'\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))', '', line.decode()),end="")
                sys.stdout.flush()
        return p.returncode
    else:
        os.system(cmd)

def convert_doc_to_kube(dicts, container_name):
    """Check whether the given file Docker Compose contains more than one containers

    Args:
        dicts (dictionary): Dictionary containing Docker Compose file

    Returns:
        string: name of the container
    """
    if dicts["version"] == "3.9":
        dicts["version"] = "3.7"
    with open("compose.yaml", "w") as out_file:
        yaml.round_trip_dump(dicts, out_file)
    cmd = "kompose convert -f compose.yaml --volumes hostPath"
    status = run_command(cmd)

    if status != 0:
        raise ValueError("Docker Compose has a validation error")
    
    cmd = "count=0; for file in `ls {}-*`; do if [ $count -eq 0 ]; then cat $file >{}.yaml; count=1; else echo '---'>>{}.yaml; cat $file >>{}.yaml; fi; done".format(
        container_name, container_name, container_name, container_name
    )
    run_command(cmd)
    os.remove("compose.yaml")


def translate_manifest(manifests, volumeData: list = None, portData: list = None, configurationData: list = None):
    """Translates K8s Manifest(s) to a MiCADO ADT

    Args:
        file (string): Path to Kubernetes manifest
    Returns:
        adt: ADT in dictionary format
    """
    adt = _get_default_adt()
    node_templates = adt["node_templates"]
    if configurationData is not None:
        _add_configdata(configurationData, node_templates)

    print("Translating the manifest")
    _transform(manifests, "micado", node_templates, volumeData, portData, configurationData)
    return adt


def _add_configdata(configurationData, node_templates):
    for conf in configurationData:
        file = conf["file_path"]
        in_path = Path(file)
        file_content = conf["file_content"]
        configmap = {
            "type": "tosca.nodes.MiCADO.Container.Config.Kubernetes",
            "properties": {
                "data": {f"{in_path.name}": f"{file_content}"}
            }
        }
        node_templates[
            in_path.name.lower().replace(".", "-").replace("_", "-").replace(" ", "-")
        ] = configmap


def _transform(
    manifests, filename, node_templates, volumeData: list = None, portData: list = None, configurationData: list = None
):
    """Transforms a single manifest into a node template

    Args:
        manifests (iter): Iterable of k8s manifests
        filename (string): Name of the file
        node_templates (dict): `node_templates` key of the ADT
    """

    wln = 0
    for ix, manifest in enumerate(manifests):
        name, count = _get_name(manifest)
        if count == 1:
            wln = wln + 1
        if wln > 1:
            print(
                "Manifest file can't have more than one workloads. Exiting ..."
            )
            raise ValueError("Manifest file has more than one workload")
        node_name = name or f"{filename}-{ix}"
        kind = manifest["kind"].lower()

        if kind in ["deployment", "pod", "statefulset", "daemonset"]:

            for vol in volumeData:
                spec = manifest["spec"]
                if spec.get("containers") is None:
                    new_spec = spec["template"]["spec"]
                    _update_volume(new_spec, vol)
                else:
                    _update_volume(spec, vol)

            for port in portData:
                spec = manifest["spec"]
                if spec.get("containers") is None:
                    new_spec = spec["template"]["spec"]
                    _update_port(new_spec, port)
                else:
                    _update_port(spec, port)

            for conf in configurationData:
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

def _update_volume(spec, vol):
    containers = spec["containers"]
    for container in containers:
        volume_mounts = container.setdefault("volumeMounts", [])
        volume_mount = volume_mounts[vol['id']]
        if volume_mount["mountPath"] == vol["mountPath"]:
            volume_mount["mountPropagation"] = vol["mountPropagation"]

def _update_port(spec, port):
    containers = spec["containers"]
    for container in containers:
        ports = container.setdefault("ports", [])
        update_port = ports[port['id']]
        if update_port["containerPort"] == port["containerport"]:
            update_port["hostPort"] = port["hostport"]

def _add_volume(spec, conf):
    containers = spec["containers"]
    for container in containers:
        volume_mounts = container.setdefault("volumeMounts", [])

        file = conf["file_path"]
        in_path = Path(file)
        directory = os.path.dirname(file)
        volume_mount = {"name": in_path.stem, "mountPath": directory}
        if (conf.get("mountPropagation") is not None) and (
            conf.get("mountPropagation")
        ):
            volume_mount["mountPropagation"] = conf["mountPropagation"]

        volume_mounts.append(volume_mount)

    volumes = spec.setdefault("volumes", [])
    volumes.append({"name": in_path.stem, "configMap": {"name": in_path.stem}})


def _get_name(manifest):
    """Returns the name from the manifest metadata

    Args:
        manifest (dict): K8s manifests

    Returns:
        string: Name of the Kubernetes object, or None
    """
    try:
        count = 0
        name = manifest["metadata"]["name"].lower()
        kind = manifest["kind"].lower()
        if kind in ["deployment", "pod", "statefulset", "daemonset"]:
            count = 1
        return f"{name}-{kind}", count
    except KeyError:
        return None, 0


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
