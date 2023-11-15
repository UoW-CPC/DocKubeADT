import re
import subprocess

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


def run_command(cmd):
    """
    Executes a shell command and returns the output and return code.

    Args:
        cmd (str): The command to execute.

    Returns:
        tuple: A tuple containing the return code and output of the command.
    """
    with subprocess.Popen(
        cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True
    ) as p:
        output = ""
        for line in p.stdout:
            # Regex gets rid of additional characters in Kompose output
            output += re.sub(r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))", "", line.decode())
    return p.returncode, output
