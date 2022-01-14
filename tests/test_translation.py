import tempfile

import pytest
import ruamel.yaml as yaml

from dockubeadt.translator import translate


def test_basic_translation():
    manifest = {
        "kind": "Pod",
        "metadata": {"name": "my-pod-name"},
        "apiVersion": "v1",
    }

    with tempfile.NamedTemporaryFile("r+") as file:
        yaml.safe_dump(manifest, file)
        file.seek(0)
        data = translate(file.name)

    yaml_adt = yaml.safe_load(data)
    nodes = yaml_adt["topology_template"]["node_templates"]
    assert "my-pod-name-pod" in nodes


def test_multi_translation():
    with open("tests/data/hello.yaml") as file:
        data = translate(file.name)

    yaml_adt = yaml.safe_load(data)
    nodes = yaml_adt["topology_template"]["node_templates"]
    assert all(
        ["busybox-sleep-less-service" in nodes, "busybox-sleep-pod" in nodes]
    )


def test_two_pod_translation():
    with pytest.raises(ValueError):
        with open("tests/data/hello_hello.yaml") as file:
            translate(file.name)
