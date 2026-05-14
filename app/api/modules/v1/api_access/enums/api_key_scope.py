from enum import Enum


class Scopes(str, Enum):
    READ_DATA_REVISION = "read:data_revision"
    DOWNLOAD_DATA_REVISION = "download:data_revision"
    READ_PROJECT = "read:project"
    DOWNLOAD_PROJECT = "download:project"
    READ_JURISDICTION = "read:jurisdiction"
    DOWNLOAD_JURISDICTION = "download:jurisdiction"
    READ_SOURCE = "read:source"
    DOWNLOAD_SOURCE = "download:source"
    ALL = "*"
