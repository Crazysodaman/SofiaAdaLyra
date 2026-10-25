"""Stable compatibility entrypoint: ``python -m sofia``.

Core is imported lazily so a Core-free Platform installation can inspect this
entrypoint and fail closed without importing cognition or opening state.
"""


def main(*args, **kwargs):
    from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration

    roles = PlatformRoleConfiguration.from_environment()
    if not roles.supports(PlatformRole.CORE_HOST):
        raise SystemExit(
            "python -m sofia requires the separately installed CORE_HOST role; "
            "use companion-runtime status on a Core-free Platform"
        )
    from sofia.core.launcher import main as core_main

    return core_main(*args, **kwargs)

if __name__ == "__main__":
    raise SystemExit(main())
