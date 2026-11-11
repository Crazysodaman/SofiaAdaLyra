#!/usr/bin/env bash
# Project Aegis | exact-source B1/offline installer shakedown (developer only).
# This runs tests using disposable publisher fixtures. It NEVER installs,
# enrolls, signs production releases, starts service or claims platform GO.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export LC_ALL=C

usage() {
  printf '%s\n' \
    'Usage: bash tools/aegis_offline_b1_shakedown.sh [--source-sha HEX40]' \
    'Runs exact-checkout source-only B1 capsule/SAFE/native-simulator tests.' \
    'No systemd, SCM, installer, Core, Fleet or production signing operations.'
}

expected=''
while (($#)); do
  case "$1" in
    --source-sha)
      (($# >= 2)) || { usage >&2; exit 2; }
      expected="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done
if [[ -n "$expected" && ! "$expected" =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'Only exact canonical 40-hex source SHA is accepted' >&2
  exit 2
fi
for executable in git bash python3.12; do
  command -v "$executable" >/dev/null || {
    printf 'Required development tool missing: %s\n' "$executable" >&2
    exit 3
  }
done
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$root"
observed="$(git rev-parse HEAD)" || exit 3
[[ "$observed" =~ ^[0-9a-f]{40}$ ]] || exit 3
if [[ -n "$expected" && "$observed" != "$expected" ]]; then
  printf 'Refusing mismatched release checkout; expected %s found %s\n' "$expected" "$observed" >&2
  exit 3
fi
# No dirty source or untracked files may silently contaminate the test claim.
if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
  printf '%s\n' 'Uncommitted or untracked source prevents exact-SHA shakedown' >&2
  exit 3
fi
printf 'AEGIS_SOURCE_SHA=%s\n' "$observed"
printf '%s\n' 'MODE=SOURCE_ONLY_DISPOSABLE_TESTS' \
  'PUBLISHER_TRUST=TEST_ONLY' 'INSTALLED_HOST_CERTIFIED=FALSE' \
  'PLATFORM_GO=NO_GO'
for shell in \
  packaging/installers/install-aegis.sh \
  packaging/installers/verify-aegis-capsule.sh \
  packaging/installers/inspect-aegis-capsule-members.sh \
  packaging/installers/stage-aegis-capsule.sh; do
  bash -n "$shell"
done
printf '%s\n' 'BASH_SYNTAX=PASS'
# The Python 3.12 runtime is mandatory. No package download or pip install.
# ast.parse is strict Python syntax validation without writing __pycache__.
python3.12 - <<'PY'
import ast
from pathlib import Path
paths = (
    "src/sofia/platform/ops/platform_installer_offline_capsule.py",
    "src/sofia/platform/ops/platform_installer_verified_stage.py",
    "src/sofia/platform/ops/platform_installer_capsule_b1_stage.py",
    "src/sofia/platform/ops/platform_installer_sealed_publication.py",
    "src/sofia/platform/ops/platform_installer_code_install.py",
    "src/sofia/platform/ops/platform_installer_native_transaction.py",
    "test/test_ops_platform_installer_capsule.py",
    "test/test_ops_platform_installer_verified_stage.py",
    "test/test_ops_platform_installer_code_install.py",
    "test/test_ops_platform_installer_integrated_chain.py",
)
for path in paths:
    ast.parse(Path(path).read_bytes(), filename=path)
print("PYTHON_SYNTAX=PASS")
PY
python3.12 -B -m pytest -q \
  test/test_ui_aegis_installer_lifecycle_contract.py \
  test/test_ops_platform_installer_bundle.py \
  test/test_ops_platform_installer_capsule.py \
  test/test_ops_platform_installer_verified_stage.py \
  test/test_ops_platform_installer_code_install.py \
  test/test_ops_platform_installer_integrated_chain.py \
  test/test_ops_platform_installer_native_transaction.py \
  test/test_ops_platform_installer_native_update.py \
  test/test_ops_platform_installer_native_service.py
printf '%s\n' \
  'RESULT=SOURCE_TESTS_PASSED' \
  'PUBLISHER_ROOT=DISPOSABLE_NOT_PRODUCTION' \
  'NATIVE_OS_INSTALLED_HOST=NOT_TESTED' \
  'OWNER_AUTHENTICATED_HOST=NOT_TESTED' \
  'LIBRARY_ACCEPTANCE=NOT_CERTIFIED' \
  'PLATFORM_GO=NO_GO'
