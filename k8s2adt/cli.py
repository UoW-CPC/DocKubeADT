import click
import sys

from .translator import translate

@click.command()
@click.argument('file')
def main(file):
    """Converts from Kubernetes manifests to a MiCADO ADT

    FILE is the path to a single/multi Kubernetes manifests (YAML)"""
    translate(file)

if __name__ == '__main__':
    args = sys.argv
    main()