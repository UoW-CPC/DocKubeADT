import os
from io import StringIO
from tempfile import NamedTemporaryFile

from dockubeadt import __version__
from dockubeadt.utils import load_multi_yaml, load_yaml, dump_yaml, run_command
from dockubeadt.compose import (
    is_compose,
    get_container_and_name,
    check_bind_propagation,
    fix_open_param_volumes,
)
from dockubeadt.kube import (
    WORKLOADS,
    count_workloads,
    get_spec_and_container,
    add_configdata,
    update_configmaps,
    update_propagation,
    fix_params_in_volumes,
)


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
        composes = load_yaml(data)
        mdt = translate_dict("docker-compose", composes)

    else:
        manifests = load_multi_yaml(data)
        mdt = translate_dict("kubernetes-manifest", manifests)

    mdt = load_yaml(mdt)
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
        container, name = get_container_and_name(topology_metadata)
        propagation = check_bind_propagation(container)
        fix_open_param_volumes(container)
        topology_metadata = convert_doc_to_kube(topology_metadata, name)

    mdt = translate_manifest(topology_metadata, propagation, configuration_data)

    buffer = StringIO()
    dump_yaml(mdt, buffer)

    print("Translation completed successfully")

    return buffer.getvalue()


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
        dump_yaml(dicts, tmpfile)
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
        manifests = load_multi_yaml(f.read())
    os.remove(out_file)
    print(f'INFO Kubernetes file "{out_file}" removed')

    return manifests


def translate_manifest(
    manifests, propagation: list = None, configuration_data: list = None
):
    """
    Translates a Kubernetes manifest file into an ADT.

    Args:
        manifests (list): A list of Kubernetes manifest files.
        propagation (list, optional): A list of Kubernetes propagation policies. Defaults to None.
        configuration_data (list, optional): A list of configuration data. Defaults to None.

    Returns:
        dict: An Azure Deployment Template (ADT) object.
    """
    if count_workloads(manifests) > 1:
        raise ValueError("Manifest file cannot have more than one workload.")

    adt = _get_default_adt()
    node_templates = adt["node_templates"]
    if configuration_data:
        add_configdata(configuration_data, node_templates)
    _transform(manifests, node_templates, propagation, configuration_data)
    return adt


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

        spec, container = get_spec_and_container(manifest)
        if not container:
            continue

        update_propagation(container, propagation)
        fix_params_in_volumes(spec, container)
        if configuration_data:
            update_configmaps(spec, container, configuration_data)

        node_templates[node_name] = _to_node(manifest)


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
    # Remove unnecessary fields for kubernetes-validate
    # This can be removed if MiCADO stops using kubernetes-validate
    manifest.pop("status", None)
    manifest["metadata"].pop("creationTimestamp", None)
    try:
        manifest["spec"]["template"]["metadata"].pop("creationTimestamp")
    except KeyError:
        pass

    return {
        "type": "tosca.nodes.MiCADO.Kubernetes",
        "interfaces": {"Kubernetes": {"create": {"inputs": manifest}}},
    }
