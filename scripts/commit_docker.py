#!/usr/bin/env python3
"""Clean working tree and commit new Docker files."""

import subprocess
import sys


def run(cmd, desc):
    print(f"  {desc}...", end=" ")
    sys.stdout.flush()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        print("OK")
        if r.stdout.strip():
            for line in r.stdout.strip().split("\n")[-3:]:
                print(f"    {line}")
    else:
        print(f"FAILED ({r.returncode})")
        if r.stderr.strip():
            for line in r.stderr.strip().split("\n"):
                print(f"    {line}")
    return r


if __name__ == "__main__":
    # Restore unrelated files
    for f in [
        ".claude/skills/improve-codebase-architecture/DEEPENING.md",
        ".claude/skills/improve-codebase-architecture/HTML-REPORT.md",
        ".claude/skills/improve-codebase-architecture/INTERFACE-DESIGN.md",
        ".claude/skills/improve-codebase-architecture/LANGUAGE.md",
        ".claude/skills/improve-codebase-architecture/SKILL.md",
        ".gitignore",
        "CLAUDE.md",
        "ROADMAP.md",
        "src/ipolitico/core/camara_client.py",
        "CONTEXT.md",
    ]:
        subprocess.run(["git", "checkout", "--", f], capture_output=True)

    # Stage new files
    run(
        [
            "git",
            "add",
            "Dockerfile",
            ".dockerignore",
            "scripts/verify-docker-build.sh",
            "scripts/cleanup-branches.sh",
            "scripts/git_cleanup.py",
            ".github/workflows/pipeline.yml",
        ],
        "Stage files",
    )

    # Commit
    run(
        [
            "git",
            "commit",
            "-m",
            "feat(docker): Dockerfile multi-stage com perfis base e analysis\n\n- Dockerfile multi-stage (base + analysis)\n- .dockerignore para build context otimizado\n- scripts/verify-docker-build.sh para validacao\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>",
        ],
        "Commit",
    )

    # Status
    run(["git", "status", "--porcelain"], "Status")
