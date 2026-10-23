"""Read-only owner diagnostics for generalization evaluation evidence."""
from __future__ import annotations

import argparse
import json

from sofia.platform.config import create_production_configuration
from sofia.learning import LearningService
from sofia.core.social.principals import local_sparks_principal

from .service import GeneralizationService


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.generalization")
    parser.add_argument("diagnostics", nargs="?", default="diagnostics")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    config = create_production_configuration()
    service = GeneralizationService(
        config.state_path, learning=LearningService(config.state_path),
        admission=None,
    )
    print(json.dumps(service.diagnostics(
        principal=local_sparks_principal(), limit=args.limit,
    ), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
