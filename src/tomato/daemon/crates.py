from pathlib import Path
from rocrate.rocrate import ROCrate
from rocrate.model import Person, ContextEntity
from typing import Union

PROFILE_URI = "https://github.com/MADICES/MADICES-2025/discussions/25"
PROFILE_VER = "0.2"


def RepositoryObject(
    crate: ROCrate, identifier: str = None, properties: dict = None
) -> ContextEntity:
    if properties is None:
        properties = {}
    properties["@type"] = "RepositoryObject"
    return ContextEntity(crate, identifier=identifier, properties=properties)


def Profile(
    crate: ROCrate, identifier: str = PROFILE_URI, properties: dict = None
) -> ContextEntity:
    if properties is None:
        properties = {}
    properties["@type"] = "Profile"
    properties["version"] = PROFILE_VER
    return ContextEntity(crate, identifier=identifier, properties=properties)


def to_rocrate(
    datafile: Path, userid: str, sampleid: str, make_child: bool = True
) -> Union[ROCrate, None]:
    crate = ROCrate()
    profile = crate.add(Profile(crate))
    author = crate.add(Person(crate, userid))
    parent = crate.add(RepositoryObject(crate, sampleid))
    target = parent
    if make_child:
        child = crate.add(RepositoryObject(crate, None))
        parent["hasPart"] = child
        target = child
    crate.add_file(
        str(datafile),
        properties={
            "encodingFormat": "application/netcdf",
            "author": author,
        },
    )
    dataset = crate.get("./")
    dataset["conformsTo"] = profile
    target["hasPart"] = dataset

    return crate
