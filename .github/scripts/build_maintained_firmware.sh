#!/usr/bin/env bash
set -euo pipefail

profile_id=${1:-}
case "$profile_id" in
  rev1_3|rev3_x) ;;
  *)
    echo "usage: build_maintained_firmware.sh rev1_3|rev3_x" >&2
    exit 2
    ;;
esac

export SDKCONFIG="sdkconfig.ci.generated-$profile_id"
export SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.$profile_id"
exec idf.py -B "build-$profile_id" build
