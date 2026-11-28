#!/usr/bin/env bash
# Tests for scripts/secret-scan.sh and scripts/hooks/*.
#
# Everything runs in isolated temporary Git repositories with local bare remotes (no network).
# Secrets are random placeholders in the project test format (fvs_test_<32 hex>); no real or realistic
# credentials are used. The real repository's Git configuration is never changed.
#
# Required environment:
#   FVS_TEST_BETTERLEAKS         path to a Betterleaks 1.10.1 binary that passed the ADR-0001 gates
#   FVS_TEST_BETTERLEAKS_SHA256  its SHA-256; must equal the value pinned in scripts/secret-scan.sh
# Recommended on macOS: run the whole file without network, e.g.
#   sandbox-exec -p '(version 1)(allow default)(deny network*)' bash scripts/tests/test_secret_scan.sh

set -u

repo_src=$(cd "$(dirname "$0")/../.." && pwd -P) || exit 2
: "${FVS_TEST_BETTERLEAKS:?set FVS_TEST_BETTERLEAKS}"
: "${FVS_TEST_BETTERLEAKS_SHA256:?set FVS_TEST_BETTERLEAKS_SHA256}"

hash_of() {
  local out
  if command -v sha256sum >/dev/null 2>&1; then out=$(sha256sum "$1") || return 1
  else out=$(shasum -a 256 "$1") || return 1; fi
  printf '%s' "${out%% *}"
}

[ "$(hash_of "$FVS_TEST_BETTERLEAKS")" = "$FVS_TEST_BETTERLEAKS_SHA256" ] || { echo "ABORT: test binary hash mismatch"; exit 2; }
PIN="$FVS_TEST_BETTERLEAKS_SHA256"
[ "$(grep -c "\"$PIN\"" "$repo_src/scripts/secret-scan.sh")" = 1 ] \
  || { echo "ABORT: test binary SHA-256 is not pinned in scripts/secret-scan.sh for any platform"; exit 2; }
case "$(uname -s)" in MINGW*|MSYS*) exe=".exe" ;; *) exe="" ;; esac

base="${TMPDIR:-/tmp}"; base="${base%/}"
T=$(mktemp -d "$base/fvs-secret-scan-test.XXXXXX") || exit 2
cleanup() { case "$T" in "$base"/fvs-secret-scan-test.*) rm -rf -- "$T" ;; esac; }
trap cleanup EXIT

pass=0; failed=0; outputs="$T/outputs"; mkdir -p "$outputs"
check() { # name expected actual
  if [ "$2" = "$3" ]; then pass=$((pass + 1)); echo "ok   $1 (got $3)"
  else failed=$((failed + 1)); echo "FAIL $1: expected $2, got $3"; fi
}

# 0. line endings and executable mode of the scripts in this checkout (Windows: core.autocrlf=true)
for f in scripts/secret-scan.sh scripts/install-betterleaks.sh scripts/hooks/pre-commit scripts/hooks/pre-push \
         scripts/tests/test_secret_scan.sh scripts/tests/test_install_betterleaks.sh; do
  check "$f: eol attribute" lf "$(git -C "$repo_src" check-attr eol -- "$f" | sed 's/.*: eol: //')"
  check "$f: no CR in working tree" 0 "$(tr -cd '\r' < "$repo_src/$f" | wc -c | tr -d ' ')"
  check "$f: index mode" 100755 "$(git -C "$repo_src" ls-files -s -- "$f" | cut -d' ' -f1)"
done

# Isolate Git from the user's global and system configuration.
export HOME="$T/home" XDG_CONFIG_HOME="$T/home/.config" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL="$T/home/.gitconfig"
export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@invalid GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@invalid
mkdir -p "$HOME" && : > "$GIT_CONFIG_GLOBAL"

mkdir -p "$T/bin"
cp "$FVS_TEST_BETTERLEAKS" "$T/bin/betterleaks$exe" && chmod 755 "$T/bin/betterleaks$exe"
export BETTERLEAKS_BIN="$T/bin/betterleaks$exe"

secret() { printf 'fvs_test_%s' "$(openssl rand -hex 16)"; }
SECRETS="$T/secrets"; : > "$SECRETS"
new_secret() { local s; s=$(secret); printf '%s\n' "$s" >> "$SECRETS"; printf '%s' "$s"; }

new_repo() { # creates a repository with the scan files committed
  local r="$T/repo-$1"
  git init -q "$r" || exit 2
  mkdir -p "$r/scripts/hooks"
  cp "$repo_src/.betterleaks.toml" "$r/"
  cp "$repo_src/scripts/secret-scan.sh" "$r/scripts/"
  cp "$repo_src/scripts/hooks/pre-commit" "$repo_src/scripts/hooks/pre-push" "$r/scripts/hooks/"
  echo "clean" > "$r/README.md"
  git -C "$r" add -A && git -C "$r" commit -q -m init || exit 2
  printf '%s' "$r"
}
scan() { # repo mode [args...]; prints exit code, saves output
  local r="$1" m="$2"; shift 2
  (cd "$r" && ./scripts/secret-scan.sh "$m" "$@") > "$outputs/$(basename "$r")-$m-$RANDOM.log" 2>&1
  echo $?
}
scan_pinned() { # hash repo mode: scan with a copy of the script whose pinned value is replaced by hash
  local h="$1" r="$2" m="$3"
  sed "s/\"$PIN\"/\"$h\"/" "$r/scripts/secret-scan.sh" > "$T/secret-scan-pinned.sh" && chmod 755 "$T/secret-scan-pinned.sh"
  [ "$(grep -c "\"$h\"" "$T/secret-scan-pinned.sh")" = 1 ] || { echo 99; return; }
  (cd "$r" && "$T/secret-scan-pinned.sh" "$m") > "$outputs/pinned-$m-$RANDOM.log" 2>&1
  echo $?
}

# 1. clean change passes
r=$(new_repo clean); echo "more clean text" >> "$r/README.md"; git -C "$r" add README.md
check "clean staged change" 0 "$(scan "$r" staged)"
check "clean history" 0 "$(scan "$r" history)"

# 2. staged placeholder secret is detected
r=$(new_repo staged); echo "token=$(new_secret)" > "$r/config.txt"; git -C "$r" add config.txt
check "staged secret detected" 3 "$(scan "$r" staged)"

# 3. unstaged and untracked secrets are not part of the staged scan
r=$(new_repo unstaged); echo "token=$(new_secret)" >> "$r/README.md"; echo "token=$(new_secret)" > "$r/untracked.txt"
echo "clean" > "$r/ok.txt"; git -C "$r" add ok.txt
check "unstaged/untracked secret ignored by staged scan" 0 "$(scan "$r" staged)"

# 4. deleted secret remains detectable in history
r=$(new_repo deleted); echo "token=$(new_secret)" > "$r/old.txt"
git -C "$r" add old.txt && git -C "$r" commit -q --no-verify -m add && git -C "$r" rm -q old.txt && git -C "$r" commit -q -m remove
check "deleted secret: staged scan" 0 "$(scan "$r" staged)"
check "deleted secret: history scan" 3 "$(scan "$r" history)"

# 4b. secret that appears only in a merge conflict resolution (evil merge)
r=$(new_repo merge); trunk=$(git -C "$r" symbolic-ref --short HEAD)
echo "base" > "$r/f.txt"; git -C "$r" add f.txt && git -C "$r" commit -q -m base
git -C "$r" switch -q -c side && echo "side" > "$r/f.txt" && git -C "$r" commit -q -am side
git -C "$r" switch -q "$trunk" && echo "trunk" > "$r/f.txt" && git -C "$r" commit -q -am trunk
git -C "$r" merge -q side > /dev/null 2>&1
echo "token=$(new_secret)" > "$r/f.txt"; git -C "$r" add f.txt
check "merge resolution: staged scan" 3 "$(scan "$r" staged)"
git -C "$r" commit -q --no-edit --no-verify
check "merge commit has two parents" 3 "$(git -C "$r" rev-list --parents -n 1 HEAD | wc -w | tr -d ' ')"
check "merge resolution: history scan" 3 "$(scan "$r" history)"

# 5. missing configuration
r=$(new_repo noconfig); git -C "$r" rm -q .betterleaks.toml && git -C "$r" commit -q -m rm
check "missing config" 2 "$(scan "$r" history)"

# 6. binary location and pinned SHA-256
r=$(new_repo binary)
check "missing binary" 2 "$(BETTERLEAKS_BIN="$T/none/betterleaks$exe" scan "$r" history)"
mkstub() { # dir script; writes a stub binary and a matching sibling hash file
  mkdir -p "$T/$1"; printf '%s\n' "$2" > "$T/$1/betterleaks"; chmod 755 "$T/$1/betterleaks"
  hash_of "$T/$1/betterleaks" > "$T/$1/betterleaks.sha256"
}
mkstub stub-ok '#!/bin/sh
[ "$1" = version ] && { echo 1.10.1; exit 0; }
exit 0'
check "unpinned binary rejected" 2 "$(BETTERLEAKS_BIN="$T/stub-ok/betterleaks" scan "$r" history)"
check "sibling hash file is not trusted" yes "$([ -f "$T/stub-ok/betterleaks.sha256" ] && echo yes)"
check "default path uses platform file name" 2 "$(unset BETTERLEAKS_BIN; XDG_CACHE_HOME="$T/nocache" scan "$r" history)"
check "default path error names betterleaks$exe" 1 "$(grep -c "nocache/fvs-tools/betterleaks-1.10.1/betterleaks$exe (" "$(ls -t "$outputs"/repo-binary-history-*.log | head -n 1)")"
mkdir -p "$T/mock-linux"
printf '#!/bin/sh\ncase "$1" in -s) echo Linux ;; -m) echo x86_64 ;; *) exit 1 ;; esac\n' > "$T/mock-linux/uname"
chmod 755 "$T/mock-linux/uname"
check "platform without pinned SHA-256 (linux_x64) rejected" 2 "$(PATH="$T/mock-linux:$PATH" scan "$r" history)"

# 7. scanner process failure and version output (stub binaries pinned in a test copy of the script)
mkstub stub-fail '#!/bin/sh
[ "$1" = version ] && { echo 1.10.1; exit 0; }
exit 1'
mkstub stub-crash '#!/bin/sh
[ "$1" = version ] && { echo 1.10.1; exit 0; }
kill -9 $$'
mkstub stub-version '#!/bin/sh
[ "$1" = version ] && { echo 9.9.9; exit 0; }
exit 0'
mkstub stub-crlf '#!/bin/sh
[ "$1" = version ] && { printf "1.10.1\r\n"; exit 0; }
exit 0'
stub_scan() { BETTERLEAKS_BIN="$T/$1/betterleaks" scan_pinned "$(hash_of "$T/$1/betterleaks")" "$r" history; }
check "pinned stub passes (control)" 0 "$(stub_scan stub-ok)"
check "scanner exits 1 (error, not leak)" 2 "$(stub_scan stub-fail)"
check "scanner killed" 2 "$(stub_scan stub-crash)"
check "unexpected version" 2 "$(stub_scan stub-version)"
check "version output with CRLF accepted" 0 "$(stub_scan stub-crlf)"
check "bad argument" 2 "$(scan "$r" everything)"

# 8. --rev validation
check "--rev with staged rejected" 2 "$(scan "$r" staged --rev "$(git -C "$r" rev-parse HEAD)")"
check "--rev malformed SHA rejected" 2 "$(scan "$r" history --rev 'HEAD;x')"
check "--rev unknown commit rejected" 2 "$(scan "$r" history --rev "$(printf '%040d' 1)")"
check "--rev missing value rejected" 2 "$(scan "$r" history --rev)"

# 9. hook blocks commit; bypass with --no-verify; full-history scan (as in CI) still detects
r=$(new_repo hook); git -C "$r" config --local core.hooksPath scripts/hooks
echo "token=$(new_secret)" > "$r/leak.txt"; git -C "$r" add leak.txt
git -C "$r" commit -q -m leak > "$outputs/hook-commit.log" 2>&1; check "pre-commit hook blocks commit" 1 "$?"
git -C "$r" commit -q --no-verify -m bypass > "$outputs/hook-bypass.log" 2>&1; check "hook bypassed with --no-verify" 0 "$?"
check "bypassed commit found by history scan" 3 "$(scan "$r" history)"
git init -q --bare "$T/remote.git" || exit 2
git -C "$r" push -q "$T/remote.git" HEAD:refs/heads/main > "$outputs/hook-push.log" 2>&1; check "pre-push hook blocks push" 1 "$?"
check "blocked push left remote empty" 0 "$(git -C "$T/remote.git" for-each-ref | wc -l | tr -d ' ')"
r=$(new_repo hookclean); git -C "$r" config --local core.hooksPath scripts/hooks
echo "fine" > "$r/ok.txt"; git -C "$r" add ok.txt
git -C "$r" commit -q -m ok > "$outputs/hook-clean.log" 2>&1; check "pre-commit hook allows clean commit" 0 "$?"

# 10. pre-push scans the pushed commits, not only commits reachable from local refs
r=$(new_repo push); git -C "$r" config --local core.hooksPath scripts/hooks
echo "token=$(new_secret)" > "$r/leak.txt"; git -C "$r" add leak.txt && git -C "$r" commit -q --no-verify -m leak
leak_sha=$(git -C "$r" rev-parse HEAD); git -C "$r" reset -q --hard HEAD~1
check "unreachable commit not covered by ref-only history scan" 0 "$(scan "$r" history)"
check "history scan with --rev detects it" 3 "$(scan "$r" history --rev "$leak_sha")"
R="$T/remote-push.git"; git init -q --bare "$R" || exit 2
push() { git -C "$r" push -q "$R" "$@" > "$outputs/push-$RANDOM.log" 2>&1; echo $?; }
remote_has() { git -C "$R" rev-parse -q --verify "$1" > /dev/null && echo yes || echo no; }
check "clean push of new ref allowed" 0 "$(push HEAD:refs/heads/main)"
check "push of unreachable secret commit blocked" 1 "$(push "$leak_sha:refs/heads/leak")"
check "blocked ref not created" no "$(remote_has refs/heads/leak)"
check "multi-ref push with one secret commit blocked" 1 "$(push HEAD:refs/heads/ok "$leak_sha:refs/heads/leak2")"
check "multi-ref: clean ref not created either" no "$(remote_has refs/heads/ok)"
git -C "$r" tag -a -m clean v-clean HEAD
check "clean annotated tag push allowed" 0 "$(push refs/tags/v-clean)"
check "tag pointing at secret commit blocked" 1 "$(push "$leak_sha:refs/tags/v-leak")"
check "branch deletion allowed" 0 "$(push :refs/heads/main)"
hook() { (cd "$r" && printf "$1" | ./scripts/hooks/pre-push origin "$R") > "$outputs/hook-input-$RANDOM.log" 2>&1; echo $?; }
z=$(printf '%040d' 0); h=$(git -C "$r" rev-parse HEAD)
check "empty input: history scan only" 0 "$(hook '')"
check "garbage input blocked" 1 "$(hook 'garbage\n')"
check "non-hex local SHA blocked" 1 "$(hook "refs/heads/x zzzz refs/heads/x $z\n")"
check "extra field blocked" 1 "$(hook "refs/heads/x $h refs/heads/x $z extra\n")"
check "unknown local commit blocked" 1 "$(hook "refs/heads/x $(printf '%040d' 1) refs/heads/x $z\n")"
check "input without trailing newline still scanned" 1 "$(hook "refs/heads/x $leak_sha refs/heads/x $z")"

# 11. configuration weakening in a change is not trusted: scanning with the base configuration still detects
r=$(new_repo weaken); cp "$r/.betterleaks.toml" "$T/base.toml"
cat > "$r/.betterleaks.toml" <<'EOF'
title = "weakened"
[extend]
useDefault = false
EOF
echo "token=$(new_secret)" > "$r/leak.txt"; git -C "$r" add -A && git -C "$r" commit -q -m weaken
check "weakened config in change misses the leak" 0 "$(scan "$r" history)"
check "base (trusted) config still detects" 3 "$(scan "$r" history --config "$T/base.toml")"

# 12. exit code survives when invoked from zsh and inside a pipeline caller
r=$(new_repo shells); echo "token=$(new_secret)" > "$r/leak.txt"; git -C "$r" add leak.txt
if command -v zsh >/dev/null 2>&1; then
  check "exit code from zsh caller" 3 "$(cd "$r" && zsh -fc './scripts/secret-scan.sh staged >/dev/null 2>&1; echo $?')"
else
  echo "skip exit code from zsh caller (zsh not installed)"
fi
check "exit code from sh caller" 3 "$(cd "$r" && sh -c './scripts/secret-scan.sh staged >/dev/null 2>&1; echo $?')"

# 13. masking: no placeholder secret appears in any captured output
leaked=0
while IFS= read -r s; do
  [ -n "$s" ] || continue
  if grep -rqF -- "$s" "$outputs"; then leaked=$((leaked + 1)); fi
done < "$SECRETS"
check "no raw secret in outputs ($(wc -l < "$SECRETS" | tr -d ' ') secrets)" 0 "$leaked"

echo "passed $pass, failed $failed"
[ "$failed" -eq 0 ]
