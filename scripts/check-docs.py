#!/usr/bin/env python3
"""Repository document checks (Python standard library only).

Checks:
  required   required files exist
  id-dup     an identifier is defined more than once
             (definition = first cell of a row in a Markdown table whose
             first header cell is "ID" or "SC"; references elsewhere are allowed)
  link       relative Markdown links point to existing files inside the root
  public     public files contain no local paths, e-mail addresses,
             co-author trailers, generated-by phrases or AI session links

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
DEFINITION_HEADERS = ("ID", "SC")
ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Za-z0-9]+)*$")
ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|")
LINK_RE = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

# Patterns are assembled from parts so that this file does not match itself.
PUBLIC_PATTERNS = (
    ("local-path", re.compile("|".join([
        "/" + "Users/[^/\\s]+",
        "/" + "home/[a-z][^/\\s]*",
        "/" + "var/folders/",
        "/" + "private/tmp/",
        "[A-Za-z]:\\\\" + "Users\\\\",
    ]))),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+" + "@" + r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")),
    ("co-author", re.compile("Co-" + "Authored-" + "By", re.IGNORECASE)),
    ("generated-by", re.compile("Generated " + "with", re.IGNORECASE)),
    ("session-link", re.compile("claude" + r"\.ai/(?:code|chat)", re.IGNORECASE)),
)


class CheckError(Exception):
    pass


def inside(root, path):
    return os.path.commonpath([root, path]) == root


def list_files(root, use_git):
    if use_git:
        try:
            out = subprocess.run(
                ["git", "-C", root, "ls-files", "-z"],
                check=True, capture_output=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as e:
            raise CheckError("git ls-files failed: %s" % e)
        rels = [p for p in out.decode("utf-8").split("\0") if p]
    else:
        rels = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") or d == ".github")
            for name in sorted(filenames):
                rels.append(os.path.relpath(os.path.join(dirpath, name), root))
    files = []
    for rel in rels:
        if not rel.endswith(TEXT_SUFFIXES):
            continue
        full = os.path.join(root, rel)
        if not inside(root, os.path.realpath(full)):
            raise CheckError("%s resolves outside the root" % rel)
        if os.path.isfile(full):
            files.append(rel.replace(os.sep, "/"))
    return files


def read_lines(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            return f.read().split("\n")
    except (OSError, UnicodeDecodeError) as e:
        raise CheckError("cannot read %s: %s" % (rel, e))


def check_required(root, required):
    return ["%s: [required] missing required file" % r
            for r in required if not os.path.isfile(os.path.join(root, r))]


def check_ids(contents):
    seen = {}
    findings = []
    for rel, lines in contents.items():
        if not rel.endswith(".md"):
            continue
        header = None
        for no, line in enumerate(lines, 1):
            if not line.startswith("|"):
                header = None
                continue
            m = ROW_RE.match(line)
            cell = m.group(1) if m else ""
            if header is None:
                header = cell
                continue
            if header not in DEFINITION_HEADERS or not ID_RE.match(cell) or not re.search(r"\d", cell):
                continue
            if cell in seen:
                findings.append("%s:%d: [id-dup] %s already defined at %s:%d" % ((rel, no, cell) + seen[cell]))
            else:
                seen[cell] = (rel, no)
    return findings, len(seen)


def check_links(root, contents):
    findings = []
    for rel, lines in contents.items():
        if not rel.endswith(".md"):
            continue
        base = os.path.dirname(os.path.join(root, rel))
        for no, line in enumerate(lines, 1):
            for target in LINK_RE.findall(line):
                if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("#"):
                    continue
                path = target.split("#", 1)[0]
                if not path:
                    continue
                full = os.path.normpath(os.path.join(base, path))
                if not inside(root, full):
                    findings.append("%s:%d: [link] %s points outside the root" % (rel, no, target))
                elif not inside(root, os.path.realpath(full)):
                    findings.append("%s:%d: [link] %s resolves outside the root" % (rel, no, target))
                elif not os.path.exists(full):
                    findings.append("%s:%d: [link] %s does not exist" % (rel, no, target))
    return findings


def check_public(contents):
    findings = []
    for rel, lines in contents.items():
        for no, line in enumerate(lines, 1):
            for rule, pattern in PUBLIC_PATTERNS:
                if pattern.search(line):
                    findings.append("%s:%d: [public:%s] matched" % (rel, no, rule))
    return findings


def run(root, use_git, required):
    root = os.path.realpath(root)
    if not os.path.isdir(root):
        raise CheckError("root is not a directory: %s" % root)
    findings = check_required(root, required)
    files = list_files(root, use_git)
    if not files:
        raise CheckError("no files to check")
    contents = {rel: read_lines(root, rel) for rel in files}
    id_findings, id_count = check_ids(contents)
    if id_count == 0:
        raise CheckError("no identifier definitions found")
    findings += id_findings
    findings += check_links(root, contents)
    findings += check_public(contents)
    return files, id_count, findings


def main(argv):
    here = os.path.dirname(os.path.realpath(__file__))
    parser = argparse.ArgumentParser(description="Repository document checks")
    parser.add_argument("--root", default=os.path.dirname(here))
    parser.add_argument("--no-git", action="store_true", help="walk the directory instead of git ls-files")
    parser.add_argument("--require", action="append", help="required file (repeatable); replaces defaults")
    args = parser.parse_args(argv)
    try:
        files, id_count, findings = run(args.root, not args.no_git, tuple(args.require or DEFAULT_REQUIRED))
    except CheckError as e:
        print("ERROR: %s" % e)
        print("RESULT: ERROR")
        return 2
    for f in findings:
        print(f)
    print("checked %d files, %d identifier definitions, %d findings" % (len(files), id_count, len(findings)))
    print("RESULT: %s" % ("FAIL" if findings else "PASS"))
    return 1 if findings else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:  # unexpected failure must not look like a pass
        print("ERROR: unexpected %s: %s" % (type(e).__name__, e))
        print("RESULT: ERROR")
        sys.exit(2)
