import tempfile

import pytest
from ruamel.yaml import YAML

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
