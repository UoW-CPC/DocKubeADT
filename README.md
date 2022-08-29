# Docker Compose and K8s manifests to (MiCADO) ADT

Translate a single or multi-part YAML file containing
Kubernetes manifests or a Docker compose into a MiCADO ADT.

## Requirements

- `Python >= 3.6`
- `click`
- `ruamel.yaml`

## Usage

Install compose binary:

    curl -L https://github.com/kubernetes/kompose/releases/download/v1.26.1/kompose-linux-amd64 -o kompose
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

## Things to note(Docker Compose)

- All the volume mounts in docker compose are by default converted to 'hostPath' volume mounts in MiCADO ADT
- Use the `restart` property in docker compose to manage the container restarts. The values can be `always`, `on-failure` or `none`.
- Use the long port syntax in docker-compose for services that needs to be exposed externally using a domain name or public IP. A sample of long port syntax is given below.
```
    ports:
     - target: 8080
       published:8080
       protocol: tcp
       mode: host
```

## Docker Compose Variables

The variables in docker compose file needs to be in these form:

    - TEST_MESSAGE={ get_input:TEST_MESSAGE }
    TEST_MESSAGE: '{ get_input:TEST_MESSAGE }'
    command: 'python3 start.py {get_input:DB_MODEL_}'


## Roadmap

- Support appending translated nodes to an existing ADT
