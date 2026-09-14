from importlib.metadata import metadata, version

from sofia.application.metadata import (
    application_name,
    application_version,
)


def test_application_name_matches_package_metadata():
    package_metadata = metadata("sofia-ada-lyra")

    assert application_name() == package_metadata["Name"]


def test_application_version_matches_package_metadata():
    assert application_version() == version("sofia-ada-lyra")


def test_application_name_is_non_empty_string():
    value = application_name()

    assert isinstance(value, str)
    assert value


def test_application_version_is_non_empty_string():
    value = application_version()

    assert isinstance(value, str)
    assert value