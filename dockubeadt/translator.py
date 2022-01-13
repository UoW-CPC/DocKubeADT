import os

import ruamel.yaml as yaml
import logging

logging.basicConfig(filename="std.log",format='%(asctime)s %(message)s',filemode='w')
log=logging.getLogger()
log.setLevel(logging.INFO)

def translate(file, stream = False):
    if not stream:
        with open(file, "r") as in_file:
            data = in_file.read()
    else:
        data = file

    dicts = yaml.safe_load_all(data)
    type = check_type(dicts)
    
    if type == 'kubernetes-manifest':
        manifests = yaml.safe_load_all(data)
        adt = translate_dict(type, manifests)
    elif type == 'docker-compose':
        composes = yaml.safe_load(data)
        adt = translate_dict(type, composes)

    return adt

def translate_dict(deployment_format, topology_metadata):
    if deployment_format == 'kubernetes-manifest':
        mdt = translate_manifest(topology_metadata)
    elif deployment_format == 'docker-compose':
        container_name = validate_compose(topology_metadata)
        convert_doc_to_kube(topology_metadata,container_name)
        file_name = "{}.yaml".format(container_name)
        with open(file_name, "r") as f:
            data_new = f.read()
        manifests = yaml.safe_load_all(data_new)
        mdt = translate_manifest(manifests)
        cmd = "rm {}*".format(container_name)
        os.system(cmd)

    return mdt

def check_type(dicts):
    """Check whether the given dictionary is a Docker Compose or K8s Manifest

    Args:
        dicts (dictionary): dictionary containing a docker compose or k8s manifest

    Returns:
        string: docker-compose or kubernetes-manifest
    """     
    dict = list(dicts)[0]
    if 'kind' in dict:
        type = "kubernetes-manifest"
    elif 'services' in dict:
        type = "docker-compose"    
    return type

def validate_compose(dicts):
    """Check whether the given file Docker Compose contains more than one containers

    Args:
        dicts (dictionary): Dictionary containing Docker Compose contents

    Returns:
        string: name of the container
    """   
    dict = dicts['services']
    if len(dict) > 1:
        log.info("Docker compose file can't have more than one containers. Exiting...")
        raise ValueError("Docker compose file has more than one container")
    name = next(iter(dict))
    return name

def convert_doc_to_kube(dicts,container_name):
    """Check whether the given file Docker Compose contains more than one containers

    Args:
        dicts (dictionary): Dictionary containing Docker Compose file

    Returns:
        string: name of the container
    """
    if dicts['version'] == '3.9':
        dicts['version'] = '3.7'
    with open('compose.yaml', "w") as out_file:
        yaml.round_trip_dump(dicts, out_file)
    cmd = "kompose convert -f compose.yaml --volumes hostPath"
    os.system(cmd)
    cmd = "count=0;for file in `ls {}-*`; do if [ $count -eq 0 ]; then cat $file >{}.yaml; count=1; else echo '---'>>{}.yaml; cat $file >>{}.yaml; fi; done".format(container_name,container_name,container_name,container_name)
    os.system(cmd)

    os.remove('compose.yaml')

def translate_manifest(manifests):
    """Translates K8s Manifest(s) to a MiCADO ADT

    Args:
        file (string): Path to Kubernetes manifest
    Returns:
        adt: ADT in dictionary format
    """
    adt = _get_default_adt()
    node_templates = adt["topology_template"]["node_templates"]
    log.info("Translating the manifest")
    
    _transform(manifests, 'micado', node_templates)

    return adt

def _transform(manifests, filename, node_templates):
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
            log.info("Manifest file can't have more than one workloads. Exiting ...")
            raise ValueError("Manifest file has more than one workload")
        node_name = name or f"{filename}-{ix}"
        node_templates[node_name] = _to_node(manifest)


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
        if kind in ['deployment','pod','statefulset','daemonset']:
            count = 1
        return f"{name}-{kind}",count
    except KeyError:
        return None,0


def _get_default_adt():
    """Returns the boilerplate for a MiCADO ADT

    Args:
        filename (string): Filename of K8s manifest(s)

    Returns:
        dict: ADT boilerplate
    """
    return {
        "topology_template": {"node_templates": {}},
    }


def _to_node(manifest):
    """Inlines the Kubernetes manifest under node_templates

    Args:
        manifest (dict): K8s manifest

    Returns:
        dict: ADT node_template
    """
    metadata = manifest['metadata']
    metadata.pop('annotations', None)
    metadata.pop('creationTimestamp', None)
    manifest['metadata'] = metadata

    if manifest.get('spec') is not None:
        spec = manifest['spec']
        if spec.get('template') is not None:
            template = spec['template']
            if template.get('metadata') is not None:
                template_metadata = template['metadata']
                template_metadata.pop('annotations', None)
                template_metadata.pop('creationTimestamp', None)
                manifest['spec']['template']['metadata'] = template_metadata

    manifest.pop('status', None)
    return {
        "type": "tosca.nodes.MiCADO.Kubernetes",
        "interfaces": {"Kubernetes": {"create": {"inputs": manifest}}},
    }
