import setuptools
import versioneer
version=versioneer.get_version()
cmdclass=versioneer.get_cmdclass()

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
        "yadg>=4.2<5.0",
        "dgbowl_schemas>=108",
        "filelock",
    ],
    extras_require={
        "testing": [
            "pytest",
        ],
        "docs": [
            "sphinx==4.5.0",
            "sphinx-rtd-theme",
            "sphinx-autodoc-typehints",
            "autodoc-pydantic"
        ]
    },
    entry_points={
        "console_scripts": [
            "tomato=tomato:run_tomato",
            "ketchup=tomato:run_ketchup",
            "tomato_job=tomato.drivers:tomato_job"
        ]
    },
)
