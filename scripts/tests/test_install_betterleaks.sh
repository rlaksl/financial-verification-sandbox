#!/usr/bin/env bash
# Control-flow tests for scripts/install-betterleaks.sh with stub curl, gh and cosign.
# No network access and no real release assets: this checks that each gate fails closed and that
# nothing is installed unless all gates pass. It does not verify real signatures or attestations.

set -u

script="$(cd "$(dirname "$0")/.." && pwd -P)/install-betterleaks.sh"
base="${TMPDIR:-/tmp}"; base="${base%/}"
T=$(mktemp -d "$base/fvs-install-test.XXXXXX") || exit 2
cleanup() { case "$T" in "$base"/fvs-install-test.*) rm -rf -- "$T" ;; esac; }
trap cleanup EXIT

mkdir -p "$T/mock"
case "$(uname -s)/$(uname -m)" in
  Darwin/arm64) archive="betterleaks_1.10.1_darwin_arm64.tar.gz"; cosign_asset="cosign-darwin-arm64" ;;
  Linux/x86_64) archive="betterleaks_1.10.1_linux_x64.tar.gz"; cosign_asset="cosign-linux-amd64" ;;
  *)
    # The installer does not support this platform (e.g. Windows). The gate control flow does not
    # depend on the platform, so run it with uname stubbed as Linux x86_64.
    echo "note: $(uname -s)/$(uname -m) is not an install target; uname stubbed as Linux/x86_64"
    printf '#!/bin/sh\ncase "$1" in -s) echo Linux ;; -m) echo x86_64 ;; *) exit 1 ;; esac\n' > "$T/mock/uname"
    chmod 755 "$T/mock/uname"
    archive="betterleaks_1.10.1_linux_x64.tar.gz"; cosign_asset="cosign-linux-amd64" ;;
esac

hash_of() {
  local out
  if command -v sha256sum >/dev/null 2>&1; then out=$(sha256sum "$1") || return 1
  else out=$(shasum -a 256 "$1") || return 1; fi
  printf '%s' "${out%% *}"
}

# Fixtures served by the stub curl.
F="$T/fixtures"; mkdir -p "$F/pkg"
printf '#!/bin/sh\necho 1.10.1\n' > "$F/pkg/betterleaks"; chmod 755 "$F/pkg/betterleaks"
tar -czf "$F/$archive" -C "$F/pkg" betterleaks
printf '%s  %s\n' "$(hash_of "$F/$archive")" "$archive" > "$F/checksums.txt"
echo '{}' > "$F/checksums.txt.sigstore.json"
printf '#!/bin/sh\nexit "${MOCK_COSIGN_RC:-0}"\n' > "$F/$cosign_asset"

cat > "$T/mock/curl" <<EOF
#!/bin/sh
out=""; url=""
while [ \$# -gt 0 ]; do case "\$1" in -o) out="\$2"; shift 2 ;; http*) url="\$1"; shift ;; *) shift ;; esac; done
cp "$F/\$(basename "\$url")" "\$out"
EOF
cat > "$T/mock/gh" <<'EOF'
#!/bin/sh
case "$*" in
  --version) [ -n "${MOCK_GH_VERSION_OUT+x}" ] && printf '%s\n' "$MOCK_GH_VERSION_OUT" \
               || printf 'gh version %s (2026-01-01)\nhttps://github.com/cli/cli/releases/latest\n' "${MOCK_GH_VERSION:-2.93.0}"
             exit 0 ;;
  *"verify-asset v3.1.6"*) exit "${MOCK_GH_COSIGN_RC:-0}" ;;
  *"verify-asset v1.10.1"*) exit "${MOCK_GH_BL_RC:-0}" ;;
esac
exit 1
EOF
chmod 755 "$T/mock/curl" "$T/mock/gh"
export PATH="$T/mock:$PATH"

pass=0; failed=0
check() {
  if [ "$2" = "$3" ]; then pass=$((pass + 1)); echo "ok   $1"
  else failed=$((failed + 1)); echo "FAIL $1: expected $2, got $3"; fi
}
run_install() { # dest; env set by caller
  bash "$script" --dest "$1" > "$T/last.log" 2>&1; echo $?
}
installed() { [ -e "$1/betterleaks" ] && echo yes || echo no; }

d="$T/v0"; check "gh 2.92.9 rejected" 1 "$(MOCK_GH_VERSION=2.92.9 run_install "$d")"; check "old gh: nothing installed" no "$(installed "$d")"
d="$T/v1"; check "gh 2.9.99 rejected (numeric, not lexical)" 1 "$(MOCK_GH_VERSION=2.9.99 run_install "$d")"
d="$T/v2"; check "unreadable gh version rejected" 1 "$(MOCK_GH_VERSION_OUT='gh dev build' run_install "$d")"; check "unreadable gh: nothing installed" no "$(installed "$d")"
d="$T/v3"; check "gh 2.100.0 accepted" 0 "$(MOCK_GH_VERSION=2.100.0 run_install "$d")"

d="$T/d0"; check "G0 cosign attestation failure aborts" 1 "$(MOCK_GH_COSIGN_RC=1 run_install "$d")"; check "G0: nothing installed" no "$(installed "$d")"
d="$T/d1"; check "G1 signature failure aborts" 1 "$(MOCK_COSIGN_RC=1 run_install "$d")"; check "G1: nothing installed" no "$(installed "$d")"
d="$T/d3"; check "G3 archive attestation failure aborts" 1 "$(MOCK_GH_BL_RC=1 run_install "$d")"; check "G3: nothing installed" no "$(installed "$d")"

cp "$F/checksums.txt" "$T/checksums.good"
printf '%064d  %s\n' 0 "$archive" > "$F/checksums.txt"
d="$T/d2"; check "G2 checksum mismatch aborts" 1 "$(run_install "$d")"; check "G2: nothing installed" no "$(installed "$d")"
: > "$F/checksums.txt"
d="$T/d2b"; check "G2 archive missing from checksums aborts" 1 "$(run_install "$d")"
cp "$T/checksums.good" "$F/checksums.txt"

d="$T/ok"; check "all gates pass installs" 0 "$(run_install "$d")"
check "installed binary present" yes "$(installed "$d")"
check "printed SHA-256 matches installed binary" yes "$(grep -qF "SHA-256 $(hash_of "$d/betterleaks");" "$T/last.log" && echo yes || echo no)"
check "no sibling hash file written" no "$([ -e "$d/betterleaks.sha256" ] && echo yes || echo no)"
check "unknown argument rejected" 1 "$(bash "$script" --bogus > /dev/null 2>&1; echo $?)"
check "no install temp dirs left" 0 "$(ls "$base" | grep -c '^fvs-betterleaks-install\.' || true)"

echo "passed $pass, failed $failed"
[ "$failed" -eq 0 ]
