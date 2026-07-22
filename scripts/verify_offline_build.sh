#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(CDPATH= cd -- "${script_dir}/.." && pwd)"
verify_root="${OFFLINE_BUILD_VERIFY_ROOT:-${project_root}/dist/offline-build-verification}"
uv_cache_dir="${UV_CACHE_DIR:-${verify_root}/uv-cache}"
uv_default_index="${UV_DEFAULT_INDEX:-https://pypi.org/simple}"
uv_bin="${UV_BIN:-uv}"

verify_root="$(realpath -m -- "${verify_root}")"
uv_cache_dir="$(realpath -m -- "${uv_cache_dir}")"

if [[ "${OFFLINE_BUILD_RESET_CACHE:-0}" == "1" ]]; then
  case "${verify_root}" in
    /|"${project_root}"|"${HOME:-}")
      echo "refusing unsafe OFFLINE_BUILD_VERIFY_ROOT: ${verify_root}" >&2
      exit 2
      ;;
  esac
  case "${uv_cache_dir}/" in
    "${verify_root}/"*) rm -rf -- "${uv_cache_dir}" ;;
    *)
      echo "refusing to reset cache outside OFFLINE_BUILD_VERIFY_ROOT: ${uv_cache_dir}" >&2
      exit 2
      ;;
  esac
fi

online_out="${verify_root}/online"
offline_out="${verify_root}/offline"
mkdir -p -- "${uv_cache_dir}" "${online_out}" "${offline_out}"

export UV_CACHE_DIR="${uv_cache_dir}"
export UV_DEFAULT_INDEX="${uv_default_index}"
unset UV_EXTRA_INDEX_URL UV_FIND_LINKS UV_INDEX UV_INDEX_URL UV_NO_BUILD_ISOLATION
unset UV_NO_BUILD_ISOLATION_PACKAGE UV_NO_CACHE UV_NO_INDEX UV_OFFLINE

cd -- "${project_root}"
"${uv_bin}" build --wheel \
  --cache-dir "${UV_CACHE_DIR}" \
  --default-index "${UV_DEFAULT_INDEX}" \
  --out-dir "${online_out}"
"${uv_bin}" build --wheel --offline \
  --cache-dir "${UV_CACHE_DIR}" \
  --default-index "${UV_DEFAULT_INDEX}" \
  --out-dir "${offline_out}"

echo "strict isolated offline build passed"
echo "index=${UV_DEFAULT_INDEX}"
echo "cache=${UV_CACHE_DIR}"
echo "artifact_dir=${offline_out}"
