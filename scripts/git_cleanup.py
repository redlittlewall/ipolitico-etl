#!/usr/bin/env python3
"""Execute git operations for cleanup and branch creation."""
import subprocess
import sys

def run(cmd, desc):
    print(f"  {desc}...", end=" ")
    sys.stdout.flush()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        print("OK")
        if r.stdout.strip():
            for line in r.stdout.strip().split("\n"):
                print(f"    {line}")
    else:
        print(f"FAILED ({r.returncode})")
        if r.stderr.strip():
            for line in r.stderr.strip().split("\n"):
                print(f"    {line}")

if __name__ == "__main__":
    # 1. Delete local branch
    run(["git", "branch", "-D", "feat/senado-integracao"], "Delete local branch")

    # 2. Delete remote branch
    run(["git", "push", "origin", "--delete", "feat/senado-integracao"], "Delete remote branch")

    # 3. Create new branch
    run(["git", "checkout", "feat/senado-api"], "Checkout senado-api")
    run(["git", "checkout", "-b", "feat/docker-setup"], "Create docker-setup branch")

    # 4. Push new branch
    run(["git", "push", "origin", "feat/docker-setup"], "Push new branch")

    # 5. List branches
    r = subprocess.run(["git", "branch", "--list"], capture_output=True, text=True)
    print("\n=== Final branches ===")
    print(r.stdout)

    print("\n=== Done ===")
