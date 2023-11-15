from ruamel.yaml import YAML

yaml = YAML()

def load_multi_yaml(data):
    """
    Load multiple YAML documents from a string.

    Args:
        data (str): The YAML data to load.

    Returns:
        list: A list of the loaded YAML documents.
    """
    return list(yaml.load_all(data))

def load_yaml(data):
    """
    Load a single YAML document from a string.

    Args:
        data (str): The YAML data to load.

    Returns:
        dict: The loaded YAML document.
    """
    return yaml.load(data)

def dump_yaml(data, stream):
    """
    Dump a YAML document to a stream.

    Args:
        data (dict): The YAML data to dump.
        stream (file): The stream to dump the YAML data to.
    """
    yaml.dump(data, stream)
