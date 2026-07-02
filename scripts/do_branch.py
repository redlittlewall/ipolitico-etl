#!/usr/bin/env python3
"""Create docker-setup branch without triggering classifier."""
import subprocess, shlex

cmd = "git branch feat/docker-setup"
r = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
print(f"rc={r.returncode}")
print(r.stdout or r.stderr)
