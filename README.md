# K8s (manifests) to (MiCADO) ADT

Translate a single or multi-part YAML file containing
Kubernetes manifests into a MiCADO ADT.

## Requirements

- `Python >= 3.6`
- `click`
- `ruamel.yaml`

## Usage

Clone the repository:

    git clone https://github.com/uowcpc/k8s2adt k8s2adt
    cd k8s2adt

Install and run k8s2adt with pip:

    pip3 install .
    k8s2adt PATH/TO/FILENAME.YAML

Or skip the install and simply:

    python3 -m k8s2adt PATH/TO/FILENAME.YAML

Generated output file will be saved to your current directory as `adt-FILENAME.YAML` 

## Roadmap

- Support appending translated nodes to an existing ADT