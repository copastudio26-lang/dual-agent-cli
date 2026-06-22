# Additions / extensions for dual_agent_core.py
import os
import subprocess
import shlex
import re

# ---------- Docker-based runner ----------
def run_script_in_docker(script_path: str, image="python:3.11-slim", timeout_s: int = 30, mem_limit="256m", cpus="0.5"):
    """
    Runs the given script inside a disposable Docker container with resource limits.
    Returns subprocess.run() style result dict.
    Requires docker to be installed and user able to run docker.
    """
    script_abs = os.path.abspath(script_path)
    workdir = os.path.dirname(script_abs)
    script_name = os.path.basename(script_abs)

    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{workdir}:/workspace:ro",
        "-w", "/workspace",
        "--network", "none",
        "--pids-limit", "64",
        "--memory", mem_limit,
        "--cpus", cpus,
        "--security-opt", "no-new-privileges",
        "--read-only",
        "--tmpfs", "/tmp:rw,size=16m",
        image,
        # Use host-side timeout too by wrapping inside container with /usr/bin/timeout if present
        "timeout", f"{timeout_s}s", "python", f"/workspace/{script_name}"
    ]
    try:
        completed = subprocess.run(docker_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout_s + 5)
        return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "timed_out": False}
    except subprocess.TimeoutExpired as e:
        return {"returncode": None, "stdout": e.stdout or "", "stderr": (e.stderr or "") + f"\nDocker-run timed out after {timeout_s}s", "timed_out": True}