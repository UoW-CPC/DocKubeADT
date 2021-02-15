import tempfile
import os
from pathlib import Path

import ruamel.yaml as yaml

from k8s2adt.translator import translate


def test_basic_translation():
    manifest = {
        "kind": "Pod",
        "metadata": {"name": "my-pod-name"},
        "apiVersion": "v1",
    }

    with tempfile.NamedTemporaryFile("r+") as file:
        yaml.safe_dump(manifest, file)
        file.seek(0)
        translate(file.name)

    output_path = f"adt-{Path(file.name).name}"
    with open(output_path) as adt:
        yaml_adt = yaml.safe_load(adt)
    os.remove(output_path)

    nodes = yaml_adt["topology_template"]["node_templates"]
    assert "my-pod-name-pod" in nodes


def test_multi_translation():
    with open("tests/data/hello.yaml") as file:
        translate(file.name)

    output_path = f"adt-{Path(file.name).name}"
    with open(output_path) as adt:
        yaml_adt = yaml.safe_load(adt)
    os.remove(output_path)

    nodes = yaml_adt["topology_template"]["node_templates"]
    assert all(
        ["busybox-sleep-less-pod" in nodes, "busybox-sleep-pod" in nodes]
    )
