import tempfile
import os
from pathlib import Path

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
        yaml_adt = translate(file.name)

    nodes = yaml_adt["topology_template"]["node_templates"]
    assert "my-pod-name-pod" in nodes


def test_multi_translation():
    with open("tests/data/hello.yaml") as file:
        yaml_adt = translate(file.name)

    nodes = yaml_adt["topology_template"]["node_templates"]
    assert all(
        ["busybox-sleep-less-pod" in nodes, "busybox-sleep-pod" in nodes]
    )
