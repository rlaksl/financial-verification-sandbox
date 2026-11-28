#!/usr/bin/env bash
# Download and verify Betterleaks v1.10.1 (D-O24, ADR-0001), then install it outside the repository.
#
# Usage: scripts/install-betterleaks.sh [--dest DIR]
#   default DIR: $XDG_CACHE_HOME or ~/.cache /fvs-tools/betterleaks-1.10.1
#
# Gates (each must pass; any failure aborts before anything is installed):
#   G0 GitHub release attestation of cosign      (gh release verify-asset)
#   G1 Sigstore signature of Betterleaks checksums.txt (cosign verify-blob, fixed identity and issuer)
#   G2 SHA-256 of the Betterleaks archive against the verified checksums.txt
#   G3 GitHub release attestation of the Betterleaks archive
# These are release attestations and signed checksums, not SLSA build provenance.
# Trust anchor: the gh CLI already installed on the machine (not verified by this script).
# gh must be 2.93.0 or later: earlier versions send the Authorization header to the TUF mirror
# in attestation/verify-asset requests (GHSA-8xvp-7hj6-mcj9).
#
# The installed binary's SHA-256 is printed. scripts/secret-scan.sh only accepts the value pinned there.
# Supported: macOS arm64, Linux x86_64. Windows uses the manual procedure in docs/process/ci-cd.md.
#
# Requires network, gh (authenticated), curl, tar and sha256sum or shasum.

set -u

readonly BL_VERSION="1.10.1"
readonly BL_REPO="betterleaks/betterleaks"
readonly BL_IDENTITY="https://github.com/betterleaks/betterleaks/.github/workflows/release.yml@refs/tags/v1.10.1"
readonly OIDC_ISSUER="https://token.actions.githubusercontent.com"
readonly COSIGN_VERSION="3.1.6"
readonly COSIGN_REPO="sigstore/cosign"
readonly GH_MIN_VERSION="2.93.0"

fail() { echo "install-betterleaks: ABORT: $*" >&2; exit 1; }

dest=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dest) [ $# -ge 2 ] || fail "--dest needs a path"; dest="$2"; shift 2 ;;
    *) fail "unknown argument: $1" ;;
  esac
done
cache="${XDG_CACHE_HOME:-${HOME:-}/.cache}"
[ -n "$dest" ] || dest="$cache/fvs-tools/betterleaks-$BL_VERSION"

case "$(uname -s)/$(uname -m)" in
  Darwin/arm64)  bl_platform="darwin_arm64"; cosign_asset="cosign-darwin-arm64" ;;
  Linux/x86_64)  bl_platform="linux_x64";    cosign_asset="cosign-linux-amd64" ;;
  *) fail "unsupported platform: $(uname -s)/$(uname -m)" ;;
esac
archive="betterleaks_${BL_VERSION}_${bl_platform}.tar.gz"

for tool in gh curl tar; do
  command -v "$tool" >/dev/null 2>&1 || fail "required tool not found: $tool"
done

# version_at_least ACTUAL MINIMUM: numeric comparison of dotted versions (no sort -V dependency).
version_at_least() {
  local IFS=. i
  local -a a=($1) m=($2)
  for i in 0 1 2; do
    [ "${a[i]:-0}" -gt "${m[i]:-0}" ] && return 0
    [ "${a[i]:-0}" -lt "${m[i]:-0}" ] && return 1
  done
  return 0
}
gh_version=$(gh --version 2>/dev/null | sed -n 's/^gh version \([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' | head -n 1)
[ -n "$gh_version" ] || fail "cannot read gh version"
version_at_least "$gh_version" "$GH_MIN_VERSION" || fail "gh $gh_version is older than $GH_MIN_VERSION"

sha256() {
  local out
  if command -v sha256sum >/dev/null 2>&1; then out=$(sha256sum "$1") || return 1
  else out=$(shasum -a 256 "$1") || return 1; fi
  printf '%s\n' "${out%% *}"
}

base="${TMPDIR:-/tmp}"; base="${base%/}"
work=$(mktemp -d "$base/fvs-betterleaks-install.XXXXXX") || fail "mktemp failed"
cleanup() {
  case "$work" in
    "$base"/fvs-betterleaks-install.*) rm -rf -- "$work" ;;
  esac
}
trap cleanup EXIT

fetch() {
  curl -fsSL --proto '=https' --tlsv1.2 -o "$work/$2" "https://github.com/$1/releases/download/$3/$2" \
    || fail "download failed: $2"
}

fetch "$COSIGN_REPO" "$cosign_asset" "v$COSIGN_VERSION"
fetch "$BL_REPO" "$archive" "v$BL_VERSION"
fetch "$BL_REPO" "checksums.txt" "v$BL_VERSION"
fetch "$BL_REPO" "checksums.txt.sigstore.json" "v$BL_VERSION"

# G0
gh release verify-asset "v$COSIGN_VERSION" "$work/$cosign_asset" --repo "$COSIGN_REPO" >/dev/null \
  || fail "G0 cosign release attestation"
chmod 700 "$work/$cosign_asset" || fail "chmod cosign"
echo "G0 pass: cosign release attestation"

# G1
"$work/$cosign_asset" verify-blob "$work/checksums.txt" \
  --bundle "$work/checksums.txt.sigstore.json" \
  --certificate-identity "$BL_IDENTITY" \
  --certificate-oidc-issuer "$OIDC_ISSUER" >/dev/null 2>&1 \
  || fail "G1 Sigstore signature of checksums.txt"
echo "G1 pass: Sigstore signature (identity and issuer fixed)"

# G2
expected=$(awk -v f="$archive" '$2 == f { print $1 }' "$work/checksums.txt") || fail "G2 read checksums"
[[ "$expected" =~ ^[0-9a-f]{64}$ ]] || fail "G2 archive not listed exactly once in checksums.txt"
actual=$(sha256 "$work/$archive") || fail "G2 hash archive"
[ "$actual" = "$expected" ] || fail "G2 archive SHA-256 mismatch"
echo "G2 pass: archive SHA-256"

# G3
gh release verify-asset "v$BL_VERSION" "$work/$archive" --repo "$BL_REPO" >/dev/null \
  || fail "G3 Betterleaks release attestation"
echo "G3 pass: Betterleaks release attestation"

mkdir -p "$work/x" || fail "mkdir"
tar -xzf "$work/$archive" -C "$work/x" betterleaks || fail "extract"
[ -f "$work/x/betterleaks" ] && [ ! -L "$work/x/betterleaks" ] || fail "unexpected archive content"

mkdir -p "$dest" || fail "cannot create $dest"
install -m 755 "$work/x/betterleaks" "$dest/betterleaks.new" || fail "install"
installed_sha=$(sha256 "$dest/betterleaks.new") || fail "hash installed binary"
mv -f "$dest/betterleaks.new" "$dest/betterleaks" || fail "finalize install"
echo "installed: $dest/betterleaks (SHA-256 $installed_sha; must match the value pinned in scripts/secret-scan.sh)"
