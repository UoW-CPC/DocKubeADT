from setuptools import setup, find_packages

setup(
    name="k8s2adt",
    description="Translate from k8s manifests to a MiCADO ADT",
    version="0.1.1",
    author="Jay DesLauriers",
    packages=find_packages(exclude=['tests']),
    install_requires=["ruamel.yaml", "click"],

    python_requires=">=3.6",
    entry_points={
        "console_scripts": ["k8s2adt=k8s2adt.cli:main"],
    },
)