#!/usr/bin/env bash
set -euo pipefail

profile_id=${1:-}
variant_id=${2:-}
case "$profile_id" in
  rev3_x) ;;
  *)
    echo "usage: build_maintained_firmware.sh rev3_x 3_4c|4c" >&2
    exit 2
    ;;
esac

case "$variant_id" in
  3_4c|4c) ;;
  *)
    echo "usage: build_maintained_firmware.sh rev3_x 3_4c|4c" >&2
    exit 2
    ;;
esac

export SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.$profile_id;sdkconfig.defaults.$variant_id"
sdkconfig_path="$(pwd)/sdkconfig.ci.generated-$variant_id-$profile_id"
exec idf.py -B "build-$variant_id-$profile_id" -D "SDKCONFIG=$sdkconfig_path" build
