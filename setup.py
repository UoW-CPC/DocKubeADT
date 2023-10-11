from setuptools import setup, find_packages

setup(
    name="dockubeadt",
    description="Translate Docker compose and k8s manifests to a MiCADO ADT",
    version="0.2.0",
    author="Resmi Arjun / Jay DesLauriers",
    packages=find_packages(exclude=['tests']),
    install_requires=["ruamel.yaml", "click"],

    python_requires=">=3.6",
    entry_points={
        "console_scripts": ["dockubeadt=dockubeadt.cli:main"],
    },
)
