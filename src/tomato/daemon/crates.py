import logging
from typing import Union

try:
    from rocrate.rocrate import ROCrate
    from rocrate.model import Person, ContextEntity

    _has_rocrate = True
except ImportError:
    _has_rocrate = False

logger = logging.getLogger(__name__)


PROFILE_URI = "https://github.com/MADICES/MADICES-2025/discussions/25"
PROFILE_VER = "0.2"


def RepositoryObject(
    crate: "ROCrate", identifier: str = None, properties: dict = None
) -> "ContextEntity":
    if properties is None:
        properties = {}
    properties["@type"] = "RepositoryObject"
    return ContextEntity(crate, identifier=identifier, properties=properties)


def Profile(
    crate: "ROCrate", identifier: str = PROFILE_URI, properties: dict = None
) -> "ContextEntity":
    if properties is None:
        properties = {}
    properties["@type"] = "Profile"
    properties["version"] = PROFILE_VER
    return ContextEntity(crate, identifier=identifier, properties=properties)


def to_rocrate(
    datapath: str, userid: str, sampleid: str, make_child: bool = True
) -> Union["ROCrate", None]:
    if _has_rocrate is False:
        return None
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
        datapath,
        properties={
            "encodingFormat": "application/netcdf",
            "author": author,
        },
    )
    dataset = crate.get("./")
    dataset["conformsTo"] = profile
    target["hasPart"] = dataset
    logger.debug("RO-crate created, writing a zip file")
    cratepath = f"{datapath[:-3]}.zip"
    crate.write_zip(cratepath)
    logger.debug("RO-crate written into '%s'", cratepath)
