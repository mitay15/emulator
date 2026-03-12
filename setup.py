from setuptools import setup, find_packages

setup(
    name="aaps_emulator",
    version="3.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "numpy",
        "matplotlib",
        "pytest",
    ],
)
