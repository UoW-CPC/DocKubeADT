# Docker Compose and K8s manifests to (MiCADO) ADT

Translate a single or multi-part YAML file containing
Kubernetes manifests or a Docker compose into a MiCADO ADT.

## Requirements

- `Python >= 3.6`
- `click`
- `ruamel.yaml`

## Usage

Install compose binary:

    curl -L https://github.com/kubernetes/kompose/releases/download/v1.24.0/kompose-linux-amd64 -o kompose
    chmod +x kompose
    sudo mv ./kompose /usr/local/bin/kompose

Clone the repository:

    git clone <repository> dockubeadt
    cd dockubeadt

Install and run dockubeadt with pip:

    pip3 install .
    dockubeadt PATH/TO/FILENAME.YAML

Or skip the install and simply:

    python3 -m dockubeadt PATH/TO/FILENAME.YAML

Generated output file will be saved to your current directory as `adt-FILENAME.YAML`

## Roadmap

- Support appending translated nodes to an existing ADT
