from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="doom_manager",
    version="0.0.1",
    description="Model Doom gameplay data as Frappe DocTypes",
    author="Observatoire des Refontes Utiles",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
