#!/usr/bin/env python3
"""Repository document checks (Python standard library only).

Checks:
  required        required files exist inside the root (git mode: and are tracked)
  missing-tracked git mode: a tracked file is missing from the working tree
  not-regular     git mode: a tracked path is not a regular file in the git index,
                  or is now a directory, symbolic link or other non-regular file
  untracked       git mode: untracked text files are reported as warnings only
  fence           a fenced code block is not closed
  id-dup          an identifier is defined more than once
                  (definition = first cell of a row in a Markdown table whose
                  first header cell is "ID" or "SC"; references elsewhere are allowed)
  id-location     an identifier with a known prefix is defined outside its file
  link            relative Markdown links point to existing files inside the root
  public          public files contain no local paths, e-mail addresses,
                  co-author trailers, generated-by phrases or AI session links

Identifier and link checks skip fenced code blocks; the public check does not.
File contents are read from the working tree, not from the git index.

Output masking: public findings report the rule name, not the matched text.
File paths, --require values, identifiers and link targets are shown as <redacted> when they
are absolute, point outside the root, or match a public pattern; this is
pattern-based, so a value that matches no pattern is shown as is. Argument
errors, git errors, read errors and unexpected exceptions report only the error
kind, exit code or exception type.
Not checked: link anchors and reference-style links.

Exit codes: 0 = pass, 1 = findings, 2 = check error (treat any non-zero as failure).
Run: python3 -I scripts/check-docs.py [--root DIR] [--no-git]
"""

import argparse
import os
import re
import subprocess
import sys

DEFAULT_REQUIRED = (
    "AGENTS.md",
    "README.md",
    "docs/status.md",
    "docs/decision-register.md",
)
TEXT_SUFFIXES = (".md", ".yml", ".yaml", ".toml", ".sh", ".py", ".txt")
REGULAR_MODES = ("100644", "100755")
STAGE_ENTRY_RE = re.compile(r"^([0-7]{6}) [0-9a-f]{40,64} [0-3]$")
DEFINITION_HEADERS = ("ID", "SC")
ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Za-z0-9]+)*$")
PREFIX_RE = re.compile(r"[A-Z]+")
# The only file whose ID/SC tables may define each identifier prefix (the leading
# capital letters). Taken from the current definition tables; a prefix not listed
# here is checked for duplicates only.
DEFINITION_HOMES = {
    "D": "docs/decision-register.md",
    "U": "docs/decision-register.md",
    "H": "docs/decision-register.md",
    "FR": "docs/requirements/requirements.md",
    "NFR": "docs/requirements/requirements.md",
    "RH": "docs/requirements/requirements.md",
    "SC": "docs/poc/plan.md",
    "FM": "docs/poc/plan.md",
    "T": "docs/research/technical-issues.md",
    "SPEC": "docs/research/spec-source-analysis.md",
    "SRC": "docs/research/spec-source-analysis.md",
    "C": "docs/research/technology-comparison.md",
    "A": "docs/security/threat-model.md",
    "B": "docs/security/threat-model.md",
    "S": "docs/security/threat-model.md",
    "POL": "docs/security/threat-model.md",
    "TA": "docs/security/threat-model.md",
    "TB": "docs/security/threat-model.md",
    "TH": "docs/security/threat-model.md",
}
ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|")
LINK_RE = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

# Patterns are assembled from parts so that this file does not match itself.
PUBLIC_PATTERNS = (
    ("local-path", re.compile("|".join([
        "/" + "Users/[^/\\s]+",
        "/" + "home/[a-z][^/\\s]*",
        "/" + "var/folders/",
        "/" + "private/tmp/",
        # Windows drive paths: any case, "/" or "\" (also JSON-escaped "\\"), mixed separators.
        "(?i:[a-z]:(?:\\\\{1,2}|/)" + "users(?:\\\\{1,2}|/))",
        # Git Bash and WSL drive mounts (single-letter drive directory, optionally under mnt).
        "(?i:(?<![\\w.-])/(?:mnt/)?[a-z]/" + "users/)",
    ]))),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+" + "@" + r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")),
    ("co-author", re.compile("Co-" + "Authored-" + "By", re.IGNORECASE)),
    ("generated-by", re.compile("Generated " + "with", re.IGNORECASE)),
    ("session-link", re.compile("claude" + r"\.ai/(?:code|chat)", re.IGNORECASE)),
)


FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)
DRIVE_RE = re.compile(r"^[A-Za-z]:")
REDACTED = "<redacted>"


class CheckError(Exception):
    pass


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse repeats the given arguments, which may be local paths.
        kind = shown(message.split(":", 1)[0])
        self.exit(2, "ERROR: invalid command-line arguments (%s); see --help\nRESULT: ERROR\n" % kind)


def inside(root, path):
    return os.path.commonpath([root, path]) == root


def is_absolute(target):
    return target.startswith(("/", "\\")) or bool(DRIVE_RE.match(target))


def shown(text):
    """Return text for output, or a placeholder if it could expose local information."""
    if is_absolute(text) or any(p.search(text) for _, p in PUBLIC_PATTERNS):
        return REDACTED
    return text


def git_ls_files(root, *options):
    # git's own messages may contain absolute paths, so only the error type
    # and exit code are reported.
    try:
        proc = subprocess.run(["git", "-C", root, "ls-files", "-z"] + list(options), capture_output=True)
    except OSError as e:
        raise CheckError("git ls-files failed: %s" % type(e).__name__)
    if proc.returncode != 0:
        raise CheckError("git ls-files failed (exit %d); is the root a git repository?" % proc.returncode)
    try:
        return [p for p in proc.stdout.decode("utf-8").split("\0") if p]
    except UnicodeDecodeError:
        raise CheckError("git ls-files output could not be decoded")


def tracked_modes(root):
    """Return {path: set of index modes} from git ls-files --stage (fail closed)."""
    modes = {}
    for entry in git_ls_files(root, "--stage"):
        meta, sep, path = entry.partition("\t")
        m = STAGE_ENTRY_RE.match(meta)
        if not sep or not path or not m:
            raise CheckError("git ls-files output could not be parsed")
        modes.setdefault(path, set()).add(m.group(1))
    return modes


def tracked_path_finding(root, rel, modes):
    """Return a finding if a tracked path is not a regular file, else None."""
    full = os.path.join(root, rel)
    if not modes <= set(REGULAR_MODES):
        return ("%s: [not-regular] tracked path is not a regular file in the git index (mode %s)"
                % (shown(rel), ",".join(sorted(modes))))
    # Checked before resolving, so a symbolic link is a finding wherever it points.
    if os.path.islink(full):
        return "%s: [not-regular] tracked path is now a symbolic link" % shown(rel)
    if not os.path.lexists(full):
        return "%s: [missing-tracked] tracked file is missing from the working tree" % shown(rel)
    if not os.path.isfile(full):
        return "%s: [not-regular] tracked path is now a directory or special file" % shown(rel)
    return None


def list_files(root, use_git):
    """Return (files, tracked, findings, warnings).

    In git mode every tracked path, whatever its suffix, must be a regular file
    in the index and in the working tree; otherwise it is a finding. Only text
    files are then read. An untracked text file is a warning. tracked is None in
    --no-git mode.
    """
    tracked = None
    findings = []
    warnings = []
    if use_git:
        modes = tracked_modes(root)
        tracked = set(modes)
        rels = []
        for rel in sorted(modes):
            finding = tracked_path_finding(root, rel, modes[rel])
            if finding:
                findings.append(finding)
            else:
                rels.append(rel)
        for rel in git_ls_files(root, "--others", "--exclude-standard"):
            if rel.endswith(TEXT_SUFFIXES):
                warnings.append("%s: [untracked] not checked until tracked" % shown(rel))
    else:
        rels = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") or d == ".github")
            for name in sorted(filenames):
                rels.append(os.path.relpath(os.path.join(dirpath, name), root))
    files = []
    for rel in rels:
        # The suffix only selects which files are read.
        if not rel.endswith(TEXT_SUFFIXES):
            continue
        full = os.path.join(root, rel)
        if not inside(root, os.path.realpath(full)):
            raise CheckError("%s resolves outside the root" % shown(rel))
        if os.path.isfile(full):
            files.append(rel.replace(os.sep, "/"))
    return files, tracked, findings, warnings


def read_lines(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            return f.read().split("\n")
    except UnicodeDecodeError:
        raise CheckError("cannot read %s: not valid UTF-8" % shown(rel))
    except OSError as e:
        raise CheckError("cannot read %s: %s" % (shown(rel), type(e).__name__))


def check_required(root, required, tracked):
    findings = []
    for r in required:
        full = os.path.normpath(os.path.join(root, r))
        if (is_absolute(r) or not inside(root, full)
                or not inside(root, os.path.realpath(full))):
            findings.append("%s: [required] required path is outside the root" % REDACTED)
            continue
        if not os.path.isfile(full):
            findings.append("%s: [required] missing required file" % shown(r))
        elif tracked is not None and r not in tracked:
            # Present in the working tree but not in the index (e.g. git rm --cached).
            findings.append("%s: [required] required file is not tracked by git" % shown(r))
    return findings


def find_fences(lines):
    """Return (fenced line numbers, line number of an unclosed opening fence or None).

    Supported subset of CommonMark fenced code blocks: an opening fence is a line
    with at most three leading spaces and three or more backticks or tildes; a
    backtick fence's info string must not contain a backtick. A closing fence uses
    the same character, is at least as long, has at most three leading spaces and
    only spaces or tabs after it. Fences inside block quotes or list items, tab
    indentation and indented code blocks are not recognised.
    """
    fenced = set()
    opening = None  # (character, length, line number)
    for no, line in enumerate(lines, 1):
        m = FENCE_RE.match(line)
        if opening is None:
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                opening = (m.group(1)[0], len(m.group(1)), no)
                fenced.add(no)
            continue
        fenced.add(no)
        if (m and m.group(1)[0] == opening[0] and len(m.group(1)) >= opening[1]
                and not m.group(2).strip(" \t")):
            opening = None
    return fenced, (opening[2] if opening else None)


def check_fences(contents):
    """Return (fenced line numbers per Markdown file, findings for unclosed fences)."""
    fences = {}
    findings = []
    for rel, lines in contents.items():
        if not rel.endswith(".md"):
            continue
        fences[rel], unclosed = find_fences(lines)
        # An unclosed fence would hide the rest of the file from the identifier
        # and link checks, so it is a finding here (CommonMark would accept it).
        if unclosed is not None:
            findings.append("%s:%d: [fence] code block is not closed" % (shown(rel), unclosed))
    return fences, findings


def check_ids(contents, fences):
    seen = {}
    findings = []
    for rel, lines in contents.items():
        if not rel.endswith(".md"):
            continue
        header = None
        for no, line in enumerate(lines, 1):
            if no in fences[rel] or not line.startswith("|"):
                header = None
                continue
            m = ROW_RE.match(line)
            cell = m.group(1) if m else ""
            if header is None:
                header = cell
                continue
            if header not in DEFINITION_HEADERS or not ID_RE.match(cell) or not re.search(r"\d", cell):
                continue
            home = DEFINITION_HOMES.get(PREFIX_RE.match(cell).group(0))
            if home is not None and rel != home:
                findings.append("%s:%d: [id-location] %s must be defined in %s"
                                % (shown(rel), no, shown(cell), home))
            if cell in seen:
                first_rel, first_no = seen[cell]
                findings.append("%s:%d: [id-dup] %s already defined at %s:%d"
                                % (shown(rel), no, shown(cell), shown(first_rel), first_no))
            else:
                seen[cell] = (rel, no)
    return findings, len(seen)


def check_links(root, contents, fences):
    findings = []
    for rel, lines in contents.items():
        if not rel.endswith(".md"):
            continue
        base = os.path.dirname(os.path.join(root, rel))
        where = shown(rel)
        for no, line in enumerate(lines, 1):
            if no in fences[rel]:
                continue
            for target in LINK_RE.findall(line):
                if target.startswith("#"):
                    continue
                # Checked before the URL scheme test: "C:" would otherwise look like a scheme.
                if is_absolute(target):
                    findings.append("%s:%d: [link] %s is an absolute path" % (where, no, REDACTED))
                    continue
                if SCHEME_RE.match(target):
                    continue
                path = target.split("#", 1)[0]
                if not path:
                    continue
                full = os.path.normpath(os.path.join(base, path))
                if not inside(root, full):
                    findings.append("%s:%d: [link] %s points outside the root" % (where, no, REDACTED))
                elif not inside(root, os.path.realpath(full)):
                    findings.append("%s:%d: [link] %s resolves outside the root" % (where, no, REDACTED))
                elif not os.path.exists(full):
                    findings.append("%s:%d: [link] %s does not exist" % (where, no, shown(target)))
    return findings


def check_public(contents):
    findings = []
    for rel, lines in contents.items():
        for no, line in enumerate(lines, 1):
            for rule, pattern in PUBLIC_PATTERNS:
                if pattern.search(line):
                    findings.append("%s:%d: [public:%s] matched" % (shown(rel), no, rule))
    return findings


def run(root, use_git, required):
    root = os.path.realpath(root)
    if not os.path.isdir(root):
        raise CheckError("root is not a directory")
    files, tracked, findings, warnings = list_files(root, use_git)
    findings = check_required(root, required, tracked) + findings
    if not files:
        raise CheckError("no files to check")
    contents = {rel: read_lines(root, rel) for rel in files}
    fences, fence_findings = check_fences(contents)
    id_findings, id_count = check_ids(contents, fences)
    if id_count == 0:
        raise CheckError("no identifier definitions found")
    findings += fence_findings
    findings += id_findings
    findings += check_links(root, contents, fences)
    findings += check_public(contents)
    return files, id_count, findings, warnings


def main(argv):
    here = os.path.dirname(os.path.realpath(__file__))
    parser = ArgumentParser(description="Repository document checks")
    parser.add_argument("--root", default=os.path.dirname(here))
    parser.add_argument("--no-git", action="store_true", help="walk the directory instead of git ls-files")
    parser.add_argument("--require", action="append", help="required file (repeatable); replaces defaults")
    args = parser.parse_args(argv)
    try:
        files, id_count, findings, warnings = run(args.root, not args.no_git, tuple(args.require or DEFAULT_REQUIRED))
    except CheckError as e:
        print("ERROR: %s" % e)
        print("RESULT: ERROR")
        return 2
    for w in warnings:
        print("WARN: %s" % w)
    for f in findings:
        print(f)
    print("checked %d files, %d identifier definitions, %d findings, %d warnings"
          % (len(files), id_count, len(findings), len(warnings)))
    print("RESULT: %s" % ("FAIL" if findings else "PASS"))
    return 1 if findings else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:  # unexpected failure must not look like a pass
        # The message may contain paths or file contents, so only the type is shown.
        print("ERROR: unexpected %s" % type(e).__name__)
        print("RESULT: ERROR")
        sys.exit(2)
