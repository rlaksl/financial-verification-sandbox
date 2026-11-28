#!/usr/bin/env bash
# Secret scan wrapper for Betterleaks v1.10.1 (D-O24 ~ D-O26, ADR-0001).
#
# Usage: scripts/secret-scan.sh <staged|history> [--config PATH] [--rev SHA]...
#   staged   staged changes only (pre-commit)
#   history  full Git history of all refs (pre-commit, pre-push, CI)
#            --rev adds commits that may not be reachable from any ref (pre-push targets)
#
# Binary: BETTERLEAKS_BIN (default: $XDG_CACHE_HOME or ~/.cache/fvs-tools/betterleaks-1.10.1/betterleaks,
# betterleaks.exe on Windows). Its SHA-256 must equal the value pinned below for the platform.
# A hash file next to the binary is not trusted: it can be replaced together with the binary.
#
# Exit codes: 0 no leaks, 3 leaks found, 2 scan or setup error. Callers treat any non-zero as failure.
# Exit codes are taken from the scanner process directly, never from a pipeline.

set -u

readonly VERSION="1.10.1"
readonly LEAK_CODE=3

fail() { echo "secret-scan: ERROR: $*" >&2; exit 2; }

# SHA-256 of the extracted binary after the ADR-0001 gates passed. Changes need review.
#   darwin_arm64: ADR-0001 execution record
#   windows_x64:  manual install record of the ZIP that passed the same gates (2026-11-27)
#   linux_x64:    tar.gz that passed the same gates on Windows (2026-11-28); extracted, not executed there
pinned_sha256() {
  case "$1" in
    darwin_arm64) echo "13ac5109fa85a590c7ba6e7f130311e0c60a2bf582c3aac073176c93b46621a8" ;;
    windows_x64) echo "d9946b77870a30838f9a6a3591ea45c9c6530abfb0cf3890d2046b3d42816049" ;;
    linux_x64) echo "506082605cad984abd6ecf979a5f00fd6d701bc3ab2104a6029b1d068b3e320c" ;;
    *) return 1 ;;
  esac
}

mode="${1:-}"
shift || true
config=""
revs=()
while [ $# -gt 0 ]; do
  case "$1" in
    --config) [ $# -ge 2 ] || fail "--config needs a path"; config="$2"; shift 2 ;;
    --rev) [ $# -ge 2 ] || fail "--rev needs a commit SHA"; revs+=("$2"); shift 2 ;;
    *) fail "unknown argument: $1" ;;
  esac
done
case "$mode" in
  staged|history) ;;
  *) fail "usage: secret-scan.sh <staged|history> [--config PATH] [--rev SHA]..." ;;
esac
[ "$mode" = "history" ] || [ ${#revs[@]} -eq 0 ] || fail "--rev is only valid with history"

root=$(git rev-parse --show-toplevel 2>/dev/null) || fail "not inside a Git repository"
[ -n "$config" ] || config="$root/.betterleaks.toml"
[ -f "$config" ] || fail "config not found: $config"

for rev in ${revs[@]+"${revs[@]}"}; do
  [[ "$rev" =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]] || fail "invalid commit SHA: $rev"
  git -C "$root" cat-file -e "$rev^{commit}" 2>/dev/null || fail "not a commit: $rev"
done

case "$(uname -s)/$(uname -m)" in
  Darwin/arm64) platform="darwin_arm64"; exe="" ;;
  Linux/x86_64) platform="linux_x64"; exe="" ;;
  MINGW64_NT*/x86_64|MSYS_NT*/x86_64) platform="windows_x64"; exe=".exe" ;;
  *) fail "unsupported platform: $(uname -s)/$(uname -m)" ;;
esac
expected=$(pinned_sha256 "$platform") || fail "no pinned SHA-256 for $platform"

cache="${XDG_CACHE_HOME:-${HOME:-}/.cache}"
bin="${BETTERLEAKS_BIN:-$cache/fvs-tools/betterleaks-$VERSION/betterleaks$exe}"
[ -f "$bin" ] && [ -x "$bin" ] || fail "binary not found or not executable: $bin (see docs/process/ci-cd.md section 3)"

if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$bin") || fail "cannot hash binary"
else
  actual=$(shasum -a 256 "$bin") || fail "cannot hash binary"
fi
actual="${actual%% *}"
[ "$actual" = "$expected" ] || fail "binary SHA-256 does not match the pinned value for $platform"

version_out=$("$bin" version 2>/dev/null) || fail "cannot run binary version"
version_out="${version_out%$'\r'}"
[ "$version_out" = "$VERSION" ] || fail "unexpected version: $version_out (expected $VERSION)"

args=(git "$root" --config "$config" --redact --exit-code "$LEAK_CODE" --no-banner --no-color)
if [ "$mode" = "staged" ]; then
  args+=(--pre-commit --staged)
else
  # -m: merges are otherwise shown as combined diffs, which the scanner skips, so content that appears
  # only in a conflict resolution would be missed. -m diffs each merge against every parent.
  args+=("--log-opts=--all -m${revs[*]+ ${revs[*]}}")
fi

# --validation is never passed: external credential validation stays disabled.
"$bin" "${args[@]}"
rc=$?

case "$rc" in
  0) echo "secret-scan: $mode: no leaks found"; exit 0 ;;
  "$LEAK_CODE") echo "secret-scan: $mode: LEAKS FOUND (output redacted)" >&2; exit "$LEAK_CODE" ;;
  *) echo "secret-scan: $mode: scanner error (exit $rc)" >&2; exit 2 ;;
esac
