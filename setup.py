import setuptools
import os

with open("VERSION", "r") as infile:
    version = infile.read().strip()

with open("README.md", "r", encoding="utf-8") as infile:
    readme = infile.read()

packagedir = "src"

setuptools.setup(
    name="tomato",
    version=version,
    author="Peter Kraus",
    author_email="peter@tondon.de",
    description="au-tomation without pain!",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/dgbowl/tomato",
    project_urls={
        "Bug Tracker": "https://github.com/dgbowl/tomato/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
    ],
    package_dir={"": packagedir},
    packages=setuptools.find_packages(where=packagedir),
    python_requires=">=3.9",
    install_requires=[
        "appdirs>=1.4.0",
        "toml",
        "pyyaml",
        "psutil",
    ],
    entry_points={
        "console_scripts": [
            "tomato=tomato:run_daemon",
            "tqsub=tomato:run_qsub",
        ]
    },
)
