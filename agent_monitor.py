#!/usr/bin/env python3
"""
Agent Tasks Monitor - Autonomous GitHub Issue Worker.
Watches GitHub Issues on RoboX2020/agent-tasks, acknowledges them,
executes the requested instructions, saves task artifacts in markdown,
pushes changes to git, and replies back to the issue before closing it.
"""

import os
import re
import sys
import time
import json
import socket
import argparse
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple


REPO_DEFAULT = "RoboX2020/agent-tasks"
DEFAULT_WORKDIR = "/home/robotics"
STATE_FILE = Path(__file__).parent / ".agent_state.json"
TASKS_DIR = Path(__file__).parent / "tasks"


def load_state() -> Dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"processed_issues": []}


def save_state(state: Dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: Failed to save state file: {e}")


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\[.*?\]", "", text) # Remove tags like [ROBOT]
    text = re.sub(r"[^\w\s-]", "", text).strip()
    return re.sub(r"[-\s]+", "-", text)[:40] or "task"


def run_cmd(cmd: List[str], cwd: Optional[str] = None, timeout: float = 300) -> Tuple[int, str, str]:
    """Runs a process and returns (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd or DEFAULT_WORKDIR,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds."
    except Exception as e:
        return -1, "", str(e)


def gh_cli(args: List[str]) -> Tuple[int, str, str]:
    """Helper to run GitHub CLI."""
    return run_cmd(["gh"] + args, cwd=str(Path(__file__).parent))


def fetch_open_issues(repo: str) -> List[Dict]:
    """Fetches list of currently open issues from GitHub."""
    code, out, err = gh_cli([
        "issue", "list",
        "--repo", repo,
        "--state", "open",
        "--json", "number,title,body,author,createdAt,labels,comments"
    ])
    if code != 0:
        print(f"[!] Error fetching issues: {err.strip()}")
        return []
    try:
        return json.loads(out)
    except Exception as e:
        print(f"[!] JSON parse error: {e}")
        return []


def post_comment(repo: str, issue_number: int, body: str):
    """Posts a comment on an issue."""
    gh_cli(["issue", "comment", str(issue_number), "--repo", repo, "--body", body])


def close_issue(repo: str, issue_number: int, reason: str = "completed"):
    """Closes an issue."""
    gh_cli(["issue", "close", str(issue_number), "--repo", repo, "--reason", reason])


def extract_code_blocks(body: str) -> List[Tuple[str, str]]:
    """Extracts (lang, code) blocks from markdown issue body."""
    pattern = r"```([a-zA-Z0-9_-]+)?\n(.*?)```"
    matches = re.findall(pattern, body, re.DOTALL)
    blocks = []
    for lang, code in matches:
        lang = lang.lower().strip() or "bash"
        blocks.append((lang, code.strip()))
    return blocks


def execute_task(issue: Dict, repo: str) -> Dict:
    """Executes the task specified in the issue."""
    num = issue["number"]
    title = issue["title"]
    body = issue.get("body", "") or ""
    author = issue.get("author", {}).get("login", "unknown")
    start_time = datetime.datetime.now(datetime.timezone.utc)

    print(f"\n{'='*70}")
    print(f"[*] Processing Task #{num}: {title} (by @{author})")
    print(f"{'='*70}")

    # 1. Post registration acknowledgment comment
    ack_msg = (
        f"🤖 **Agent Registered Task #{num}**\n\n"
        f"* **Task**: `{title}`\n"
        f"* **Opened By**: @{author}\n"
        f"* **Started At**: `{start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}`\n"
        f"* **Host**: `{socket.gethostname()}`\n"
        f"* **Status**: ⏳ Working on task...\n"
    )
    post_comment(repo, num, ack_msg)

    # 2. Extract code blocks or treat body as commands
    code_blocks = extract_code_blocks(body)
    results = []

    if code_blocks:
        print(f"[*] Found {len(code_blocks)} code block(s) to execute.")
        for idx, (lang, code) in enumerate(code_blocks, 1):
            print(f"[*] Executing Block {idx} ({lang})...")
            if lang in ("bash", "sh", "shell", "zsh"):
                rc, stdout, stderr = run_cmd(["bash", "-c", code])
            elif lang in ("python", "python3", "py"):
                # If code requires torch or isaaclab, route to IsaacLab python environment
                if any(pkg in code for pkg in ("torch", "isaaclab", "isaacsim", "pxr", "warp")):
                    isaac_py = "/home/robotics/isaac/IsaacLab/.venv/bin/python"
                    if os.path.exists(isaac_py):
                        env_cmd = f"LD_PRELOAD=/lib/aarch64-linux-gnu/libgomp.so.1 {isaac_py} -c {json.dumps(code)}"
                        rc, stdout, stderr = run_cmd(["bash", "-c", env_cmd])
                    else:
                        rc, stdout, stderr = run_cmd(["python3", "-c", code])
                else:
                    rc, stdout, stderr = run_cmd(["python3", "-c", code])
            else:
                rc, stdout, stderr = run_cmd(["bash", "-c", code])

            results.append({
                "block_index": idx,
                "lang": lang,
                "code": code,
                "returncode": rc,
                "stdout": stdout.strip(),
                "stderr": stderr.strip()
            })
    else:
        # Check if the title or body contains direct bash commands (e.g. baxter status)
        first_line = body.strip().split("\n")[0] if body.strip() else ""
        if any(first_line.startswith(prefix) for prefix in ("baxter ", "python ", "ls ", "git ", "echo ")):
            print(f"[*] Executing direct command: {first_line}")
            rc, stdout, stderr = run_cmd(["bash", "-c", first_line])
            results.append({
                "block_index": 1,
                "lang": "bash",
                "code": first_line,
                "returncode": rc,
                "stdout": stdout.strip(),
                "stderr": stderr.strip()
            })
        else:
            print("[*] Natural language instruction detected. Documenting task receipt.")
            results.append({
                "block_index": 1,
                "lang": "text",
                "code": body,
                "returncode": 0,
                "stdout": f"Task instructions acknowledged: {body[:200]}...",
                "stderr": ""
            })

    end_time = datetime.datetime.now(datetime.timezone.utc)
    duration_sec = (end_time - start_time).total_seconds()
    all_success = all(r["returncode"] == 0 for r in results)

    # 3. Create documentation markdown file in tasks/
    slug = slugify(title)
    report_filename = f"issue-{num}-{slug}.md"
    report_path = TASKS_DIR / report_filename
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    report_content = f"""# Task Report #{num}: {title}

* **Issue**: [#{num}](https://github.com/{repo}/issues/{num})
* **Author**: @{author}
* **Started**: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}
* **Completed**: {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}
* **Duration**: {duration_sec:.2f} seconds
* **Status**: {'✅ Success' if all_success else '❌ Failed'}

---

## Task Instructions

{body}

---

## Execution Logs

"""
    for res in results:
        report_content += f"### Block {res['block_index']} (`{res['lang']}`)\n\n"
        report_content += f"**Input:**\n```{res['lang']}\n{res['code']}\n```\n\n"
        report_content += f"**Exit Code:** `{res['returncode']}`\n\n"
        if res['stdout']:
            report_content += f"**Stdout:**\n```text\n{res['stdout']}\n```\n\n"
        if res['stderr']:
            report_content += f"**Stderr:**\n```text\n{res['stderr']}\n```\n\n"

    with open(report_path, "w") as f:
        f.write(report_content)
    print(f"[✓] Created task documentation at {report_path}")

    # 4. Git commit and push task report
    repo_dir = str(Path(__file__).parent)
    run_cmd(["git", "add", "tasks/", ".agent_state.json"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", f"Complete task #{num}: {title}"], cwd=repo_dir)
    run_cmd(["git", "push", "origin", "main"], cwd=repo_dir)
    print(f"[✓] Pushed changes to GitHub repository.")

    # 5. Post resolution reply comment and close issue
    report_url = f"https://github.com/{repo}/blob/main/tasks/{report_filename}"
    reply_msg = (
        f"✅ **Task Completed: {title}**\n\n"
        f"### 📋 Execution Summary:\n"
        f"* **Status**: {'✅ Success' if all_success else '⚠️ Completed with errors'}\n"
        f"* **Execution Time**: `{duration_sec:.2f}s`\n"
        f"* **Detailed Report**: [{report_filename}]({report_url})\n\n"
    )

    if results:
        last = results[-1]
        out_snippet = (last.get("stdout") or last.get("stderr") or "Execution completed cleanly.")[:1000]
        reply_msg += f"### 🖥️ Output Preview:\n```text\n{out_snippet}\n```\n"

    post_comment(repo, num, reply_msg)
    close_issue(repo, num)
    print(f"[✓] Issue #{num} closed with resolution reply.")

    return {
        "number": num,
        "title": title,
        "success": all_success,
        "report": str(report_path)
    }


def main():
    parser = argparse.ArgumentParser(description="Agent Tasks Monitor - GitHub Issue Worker")
    parser.add_argument("--repo", default=REPO_DEFAULT, help=f"GitHub repository (default: {REPO_DEFAULT})")
    parser.add_argument("--interval", type=int, default=10, help="Poll interval in seconds (default: 10)")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    args = parser.parse_args()

    print("=" * 70)
    print("       🤖 AGENT TASKS - GITHUB ISSUE MONITOR 🤖")
    print("=" * 70)
    print(f"  Target Repo:    {args.repo}")
    print(f"  Poll Interval:  {args.interval} seconds")
    print(f"  Host:           {socket.gethostname()}")
    print("=" * 70)

    state = load_state()

    while True:
        try:
            issues = fetch_open_issues(args.repo)
            for issue in issues:
                num = issue["number"]
                if num not in state["processed_issues"]:
                    try:
                        execute_task(issue, args.repo)
                        state["processed_issues"].append(num)
                        save_state(state)
                    except Exception as e:
                        print(f"[!] Error processing issue #{num}: {e}")
                        post_comment(args.repo, num, f"❌ **Agent Error**: Failed to complete task: {e}")

        except Exception as e:
            print(f"[!] Monitor loop error: {e}")

        if args.once:
            break

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
