"""
dual_agent_core.py

Core dual-agent engine:
- Developer persona: generates raw Python scripts (no markdown).
- Auditor persona: inspects candidate script text and returns status labels (APPROVED / REJECTED).
- Secure subprocess controller with 30s timeout.
- Self-healing retry loop (up to 3 attempts) capturing stderr per attempt and storing logs.

API (exported):
- developer_generate_script(name: str, code_str: str, out_dir: str = ".") -> filepath
- auditor_check_script(code_str: str) -> dict {'status': 'APPROVED'|'REJECTED', 'reasons': [...]}
- self_heal_execute(script_path: str, max_retries: int = 3, timeout_s: int = 30) -> dict
- safe_execute_script_from_code(code_str: str, name: str = "agent_script.py", out_dir: str = ".", max_retries: int = 3, timeout_s: int = 30) -> dict
"""

import ast
import os
import re
import subprocess
import tempfile
import time
import traceback
from typing import Dict, List

# Safety patterns considered disallowed or suspicious for automatic execution.
_DISALLOWED_PATTERNS = [
    r"\brm\s+-rf\b",          # destructive shell rm -rf
    r"\bsubprocess\.Popen\b", # raw popen usage flagged
    r"\bos\.system\b",        # os.system usage flagged
    r"\bexec\b",              # exec usage
    r"\beval\b",              # eval usage
    r"\bcompile\b",           # dynamic compile
    r"\bshutil\.rmtree\b",
    r"\bopen\(\s*['\"]/dev",  # direct device file access
    r"\brequests\.delete\b",  # destructive HTTP verbs
]

def developer_generate_script(name: str, code_str: str, out_dir: str = ".") -> str:
    """
    Developer persona: writes a clean raw Python script to disk (no markdown).
    Returns the path to the written file.
    """
    if not name.endswith(".py"):
        name = f"{name}.py"
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    # write exactly the code_str as-is
    with open(path, "w", encoding="utf-8") as f:
        f.write(code_str)
    return os.path.abspath(path)

def auditor_check_script(code_str: str) -> Dict:
    """
    Auditor persona: checks the code string and returns:
    {'status': 'APPROVED'|'REJECTED', 'reasons': [ ... ]}
    """
    reasons: List[str] = []
    # 1) Disallowed pattern checks (regex)
    for pattern in _DISALLOWED_PATTERNS:
        if re.search(pattern, code_str, flags=re.IGNORECASE):
            reasons.append(f"Disallowed pattern detected: /{pattern}/")

    # 2) Syntax check via ast.parse
    try:
        ast.parse(code_str)
    except SyntaxError as e:
        reasons.append(f"SyntaxError: {e.msg} (line {e.lineno})")

    # 3) Heuristic checks
    if len(code_str.strip()) == 0:
        reasons.append("Script is empty.")

    # Final status
    status = "APPROVED" if not reasons else "REJECTED"
    return {"status": status, "reasons": reasons}

def _run_subprocess_cmd(cmd: List[str], timeout_s: int = 30) -> Dict:
    """
    Runs a subprocess command with timeout. Returns dict with:
    { 'returncode', 'stdout', 'stderr', 'timed_out' }
    """
    try:
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as e:
        # Kill and return timed out
        return {
            "returncode": None,
            "stdout": e.stdout or "",
            "stderr": (e.stderr or "") + f"\nProcess timed out after {timeout_s} seconds.",
            "timed_out": True,
        }
    except Exception as e:
        return {
            "returncode": None,
            "stdout": "",
            "stderr": f"Subprocess invocation error: {e}\n{traceback.format_exc()}",
            "timed_out": False,
        }

def self_heal_execute(script_path: str, max_retries: int = 3, timeout_s: int = 30) -> Dict:
    """
    Execute a local Python script safely with up to `max_retries` attempts.
    Captures stdout/stderr per attempt and returns a structured result.

    Returned dict:
    {
      'success': bool,
      'attempts': [
         { 'attempt': 1, 'returncode': 0, 'stdout': '...', 'stderr': '...', 'timed_out': False, 'timestamp': ... },
         ...
      ],
      'final_status': 'SUCCESS'|'FAILED',
    }
    """
    attempts = []
    cmd = ["python", script_path]

    for attempt in range(1, max_retries + 1):
        ts = time.time()
        result = _run_subprocess_cmd(cmd, timeout_s=timeout_s)
        attempts.append({
            "attempt": attempt,
            "returncode": result.get("returncode"),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "timed_out": result.get("timed_out", False),
            "timestamp": ts,
        })

        # Success if returncode == 0 and not timed out
        if result.get("returncode") == 0 and not result.get("timed_out"):
            return {"success": True, "attempts": attempts, "final_status": "SUCCESS"}

        # If failed and not last attempt, brief pause (exponential backoff)
        if attempt < max_retries:
            time.sleep(0.5 * attempt)

    # all attempts exhausted
    return {"success": False, "attempts": attempts, "final_status": "FAILED"}

def safe_execute_script_from_code(code_str: str, name: str = "agent_script.py", out_dir: str = ".", max_retries: int = 3, timeout_s: int = 30) -> Dict:
    """
    Full flow:
    1) Auditor checks the code. If REJECTED, returns auditor verdict and does not execute.
    2) If APPROVED, writes the file and runs self_heal_execute.
    3) Returns aggregated result with auditor verdict, file path (if written), and execution detail.
    """
    audit = auditor_check_script(code_str)
    if audit["status"] != "APPROVED":
        return {"auditor": audit, "executed": False, "execution_result": None}

    # write script to disk
    script_path = developer_generate_script(name, code_str, out_dir=out_dir)
    exec_result = self_heal_execute(script_path, max_retries=max_retries, timeout_s=timeout_s)
    return {"auditor": audit, "executed": True, "script_path": script_path, "execution_result": exec_result}


# If run as module, expose a small demonstration function (safe)
def demo_sample_script() -> str:
    return '''#!/usr/bin/env python3
import time
print("Hello from Developer persona: starting quick job...")
time.sleep(0.5)
print("Job done — this is a safe sample script.")
'''

if __name__ == "__main__":
    # quick demo when executed directly
    sample = demo_sample_script()
    print("Auditor check:", auditor_check_script(sample))
    path = developer_generate_script("sample_agent_script.py", sample, out_dir=".")
    print("Wrote sample to", path)
    res = self_heal_execute(path, max_retries=2, timeout_s=10)
    print("Execution result:", res)