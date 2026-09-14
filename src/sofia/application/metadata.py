from importlib.metadata import PackageNotFoundError
from importlib.metadata import metadata


_PACKAGE_NAME = "sofia-ada-lyra"


def application_name() -> str:
    """
    Return Sofía's authoritative application package name.
    """

    try:
        value = metadata(_PACKAGE_NAME)["Name"]
    except PackageNotFoundError as exc:
        raise RuntimeError(
            f"Application package metadata not found: {_PACKAGE_NAME!r}."
        ) from exc

    if not value:
        raise RuntimeError(
            "Application package metadata contains no package name."
        )

    return value


def application_version() -> str:
    """
    Return Sofía's authoritative application package version.
    """

    try:
        value = metadata(_PACKAGE_NAME)["Version"]
    except PackageNotFoundError as exc:
        raise RuntimeError(
            f"Application package metadata not found: {_PACKAGE_NAME!r}."
        ) from exc

    if not value:
        raise RuntimeError(
            "Application package metadata contains no version."
        )

    return value