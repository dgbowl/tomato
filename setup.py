import setuptools
import versioneer

version = versioneer.get_version()
cmdclass = versioneer.get_cmdclass()

with open("README.md", "r", encoding="utf-8") as infile:
    readme = infile.read()

packagedir = "src"

setuptools.setup(
    name="tomato",
    version=version,
    cmdclass=cmdclass,
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
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
    ],
    package_dir={"": packagedir},
    packages=setuptools.find_packages(where=packagedir),
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=[
        "appdirs>=1.4.0",
        "toml~=0.10",
        "pyyaml~=6.0",
        "psutil~=5.9",
        "dgbowl_schemas>=108",
        "filelock~=3.12",
        "pyzmq~=25.1",
        "xarray~=2024.2",
    ],
    extras_require={
        "testing": [
            "pytest~=7.4",
        ],
        "docs": [
            "sphinx~=7.2",
            "sphinx-rtd-theme~=1.3.0",
            "sphinx-autodoc-typehints < 1.20.0",
            "autodoc-pydantic==1.9.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "tomato=tomato:run_tomato",
            "ketchup=tomato:run_ketchup",
            "tomato-job=tomato.drivers:tomato_job",
            "tomato-driver=tomato.daemon.driver:tomato_driver",
            "tomato-daemon=tomato.daemon:run_daemon",
        ]
    },
)
