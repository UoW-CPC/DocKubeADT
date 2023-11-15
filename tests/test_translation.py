import tempfile

import pytest

from dockubeadt.translator import translate, translate_dict
from dockubeadt.utils import load_yaml, dump_yaml


def test_basic_translation():
    manifest = {
        "kind": "Pod",
        "metadata": {"name": "my-pod-name"},
        "apiVersion": "v1",
        "spec": {"containers":[{"image": "busybox"}]}
    }

    with tempfile.NamedTemporaryFile("r+") as file:
        dump_yaml(manifest, file)
        data = translate(file.name)

    nodes = data["topology_template"]["node_templates"]
    assert "my-pod-name-pod" in nodes


def test_multi_translation():
    with open("tests/data/hello.yaml") as file:
        data = translate(file.name)

    nodes = data["topology_template"]["node_templates"]
    print(nodes)
    assert all(["busybox-sleep-service" in nodes, "busybox-sleep-pod" in nodes])


def test_two_pod_translation():
    with pytest.raises(ValueError):
        translate("tests/data/hello_hello.yaml")


def test_compose_translation():
    data = translate("tests/data/docker-compose.yaml")
    nodes = data["topology_template"]["node_templates"]
    assert all(["db-service" in nodes, "db-deployment" in nodes])

def test_configmap_creation():

    config = [
        {
        "file_path": "/var/etc/mysql/my.cnf",
        "file_content": "[MYSQL]\nsettings=True",
        }
    ]

    with open("tests/data/docker-compose.yaml") as file:
        data = load_yaml(file)
    topo_tpl = load_yaml(translate_dict("docker-compose", data, config))
    nodes = topo_tpl["node_templates"]
    db_node = nodes["db-deployment"]
    spec = db_node["interfaces"]["Kubernetes"]["create"]["inputs"]["spec"]["template"]["spec"]
    cf_vol = spec["volumes"][-1]["configMap"]
    cf_mount = spec["containers"][0]["volumeMounts"][-1]
    assert all(
        [
            "my-cnf" in nodes,
            cf_vol["name"] == "my-cnf",
            cf_mount["subPath"] == "my.cnf",
            cf_mount["mountPath"] == "/var/etc/mysql/my.cnf"
        ]
    )
