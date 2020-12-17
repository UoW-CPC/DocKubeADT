import os
from pathlib import Path

import ruamel.yaml as yaml


def translate(file):
    """Translates from K8s Manifest(s) to a MiCADO ADT

    Args:
        file (string): Path to Kubernetes manifest
    """
    in_path = Path(file)
    adt = _get_default_adt(in_path.name)
    node_templates = adt["topology_template"]["node_templates"]
    with open(file, "r") as in_file:
        manifests = yaml.safe_load_all(in_file)
        _transform(manifests, in_path.stem, node_templates)

    out_path = Path(f"{os.getcwd()}/adt-{in_path.name}")
    with open(out_path, "w") as out_file:
        yaml.round_trip_dump(adt, out_file)


def _transform(manifests, filename, node_templates):
    """Transforms a single manifest into a node template

    Args:
        manifests (iter): Iterable of k8s manifests
        filename (string): Name of the input file
        node_templates (dict): `node_templates` key of the ADT
    """
    for ix, manifest in enumerate(manifests):
        node_name = _get_name(manifest) or f"{filename}-{ix}"
        node_templates[node_name] = _to_node(manifest)


def _get_name(manifest):
    """Returns the name from the manifest metadata

    Args:
        manifest (dict): K8s manifests

    Returns:
        string: Name of the Kubernetes object, or None
    """
    return manifest["metadata"].get("name")


def _get_default_adt(filename):
    """Returns the boilerplate for a MiCADO ADT

    Args:
        filename (string): Filename of K8s manifest(s)

    Returns:
        dict: ADT boilerplate
    """
    return {
        "tosca_definitions_version": "tosca_simple_yaml_1_2",
        "imports": [
            "https://raw.githubusercontent.com/micado-scale/tosca/develop/micado_types.yaml"
        ],
        "repositories": {"docker_hub": "https://hub.docker.com/"},
        "description": f"Generated from K8s manifests: {filename}",
        "topology_template": {"node_templates": {}},
    }


def _to_node(manifest):
    """Inlines the Kubernetes manifest under node_templates

    Args:
        manifest (dict): K8s manifest

    Returns:
        dict: ADT node_template
    """
    return {
        "type": "tosca.nodes.MiCADO.Kubernetes",
        "interfaces": {"Kubernetes": {"create": {"inputs": manifest}}},
    }
