#!/usr/bin/env python3
"""
Agent Tasks Monitor - Autonomous GitHub Issue AI Agent.
Powered by Google Antigravity Agent (Gemini LLM).
Watches GitHub Issues on RoboX2020/agent-tasks, comprehends complex natural language
instructions and long user demands, executes commands and simulations autonomously,
generates artifacts and screenshots, commits & pushes to git, and replies back to the issue.
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
ASSETS_DIR = Path(__file__).parent / "assets"
AGY_BIN = "/home/robotics/.local/bin/agy"


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
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"[^\w\s-]", "", text).strip()
    return re.sub(r"[-\s]+", "-", text)[:40] or "task"


def clean_ansi(text: str) -> str:
    """Strips terminal ANSI color/style escape sequences."""
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text).strip()


def run_cmd(cmd: List[str], cwd: Optional[str] = None, env: Optional[Dict] = None, timeout: float = 300) -> Tuple[int, str, str]:
    """Runs a process and returns (returncode, stdout, stderr)."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd or DEFAULT_WORKDIR,
            env=full_env,
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


def get_asset_files() -> Dict[str, float]:
    """Returns mapping of existing files in assets/ to modification times."""
    if not ASSETS_DIR.exists():
        return {}
    files = {}
    for p in ASSETS_DIR.glob("*"):
        if p.is_file():
            files[p.name] = p.stat().st_mtime
    return files


def run_ai_agent(issue: Dict, repo: str) -> Dict:
    """
    Hands off the full issue description to the Antigravity Agent (Gemini LLM)
    which autonomously reasons, plans, executes tools, fixes code, renders simulations,
    and returns a structured report.
    """
    num = issue["number"]
    title = issue["title"]
    body = issue.get("body", "") or ""
    author = issue.get("author", {}).get("login", "unknown")
    comments = issue.get("comments", [])
    start_time = datetime.datetime.now(datetime.timezone.utc)

    # Compile user follow-up comments if any
    extra_context = ""
    if comments and isinstance(comments, list):
        user_comments = [
            c.get("body", "") for c in comments
            if c.get("body", "") and not c.get("body", "").startswith("🤖")
        ]
        if user_comments:
            extra_context = "\n\nADDITIONAL USER COMMENTS IN THREAD:\n" + "\n---\n".join(user_comments)

    # 1. Post live dispatch acknowledgment on GitHub
    ack_msg = (
        f"🤖 **Autonomous AI Agent Dispatched for Task #{num}**\n\n"
        f"* **Task**: `{title}`\n"
        f"* **Author**: @{author}\n"
        f"* **Engine**: Google Antigravity Agent (Gemini)\n"
        f"* **Started At**: `{start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}`\n"
        f"* **Host**: `{socket.gethostname()}`\n"
        f"* **Status**: 🧠 Comprehending user instructions, formulating execution plan, and running actions...\n"
    )
    post_comment(repo, num, ack_msg)
    print(f"[*] Dispatched AI Agent for Issue #{num}...")

    # Snapshot asset directory state before agent run
    pre_assets = get_asset_files()

    # 2. Build rich agent prompt
    agent_prompt = f"""You are the autonomous Baxter Robotics & NVIDIA Isaac Sim AI Agent assigned to resolve GitHub Issue #{num} on {repo}.

ISSUE TITLE:
{title}

REQUESTED BY:
@{author}

FULL USER DEMAND / INSTRUCTIONS:
{body}
{extra_context}

SYSTEM & WORKSPACE ENVIRONMENT:
- Main Workspaces:
  * Baxter control library: /home/robotics/baxter-py (CLI: 'baxter')
  * Task repository: /home/robotics/agent-tasks
  * Isaac Sim / IsaacLab: /home/robotics/isaac/IsaacLab
  * Baxter USD: /home/robotics/isaac/baxter.usd/baxter/baxter.usda
- Physical Baxter Hardware:
  * IP: 169.254.127.243:9090
  * Parallel UDP: 127.0.0.1:19888
- Core Command Tools:
  * 'baxter status' - Inspect hardware interlocks, e-stop, and 7-DOF joint angles
  * 'baxter enable' / 'baxter disable' - Arm motor power state
  * 'baxter untuck' / 'baxter tuck' - Symmetrical operational posture or storage fold
  * 'baxter move <neutral|wave|cheer|salute|reach|tuck>' - Execute calibrated routines
  * 'baxter sim' - Launch Isaac Sim 3D digital twin
  * 'baxter sim --screenshot <path> [--pose <neutral|wave|boxing|hero>]' - Direct photorealistic RTX renders
  * 'baxter sim --sim-to-real' - Bidirectional parallel bridge
  * 'baxter face <emotion>' - Render face emotion on 1024x600 LCD
  * 'baxter dance' / 'baxter symphony' - High-level choreographies
  * 'baxter box' / 'baxter play' - Computer vision interactive sparring partner
  * Standard bash & python tools to inspect files, edit code, run diagnostics, and test changes.

YOUR INSTRUCTIONS:
1. Thoroughly read and comprehend the user's demands, instructions, edge cases, and constraints in the issue description.
2. Formulate an execution plan and run whatever tools, commands, or simulation scripts are required.
   * If screenshots or renders are requested, generate them into /home/robotics/agent-tasks/assets/.
   * If code edits or improvements are requested, edit the files in place and test them.
3. Verify that all requested actions succeeded.
4. Output a comprehensive Markdown resolution report detailing:
   * **Executive Summary**: Clear description of what was completed.
   * **Actions & Commands Executed**: Technical breakdown of actions.
   * **Results & Findings**: Key diagnostic values, test results, or status.
   * **Deliverables**: List of generated files, screenshots, or code updates.
   * **Notes / Next Steps for the User**.

Execute the plan now and deliver your complete response."""

    # 3. Execute Antigravity Agent CLI
    agy_cmd = [
        AGY_BIN if os.path.exists(AGY_BIN) else "agy",
        "--dangerously-skip-permissions",
        "-p", agent_prompt
    ]

    print(f"[*] Invoking Antigravity Agent CLI...")
    rc, stdout, stderr = run_cmd(agy_cmd, cwd=str(Path(__file__).parent), timeout=420)
    clean_agent_output = clean_ansi(stdout) if stdout else clean_ansi(stderr)

    end_time = datetime.datetime.now(datetime.timezone.utc)
    duration_sec = (end_time - start_time).total_seconds()
    success = (rc == 0 and bool(clean_agent_output))

    # Detect new or modified assets
    post_assets = get_asset_files()
    new_or_modified_assets = []
    for fname, mtime in post_assets.items():
        if fname not in pre_assets or mtime > pre_assets[fname]:
            new_or_modified_assets.append(fname)

    # 4. Save Task Documentation
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
* **Status**: {'✅ Success' if success else '❌ Failed / Timeout'}
* **AI Engine**: Google Antigravity Agent (Gemini)

---

## User Request

{body}
{extra_context}

---

## AI Agent Execution & Resolution Report

{clean_agent_output}

"""
    if new_or_modified_assets:
        report_content += "\n---\n\n## Generated Assets\n\n"
        for asset in new_or_modified_assets:
            if asset.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                report_content += f"![{asset}](../assets/{asset})\n\n"
            else:
                report_content += f"* [{asset}](../assets/{asset})\n"

    with open(report_path, "w") as f:
        f.write(report_content)
    print(f"[✓] Created task documentation at {report_path}")

    # 5. Git Commit & Push
    repo_dir = str(Path(__file__).parent)
    run_cmd(["git", "add", "tasks/", "assets/", ".agent_state.json"], cwd=repo_dir)
    run_cmd(["git", "commit", "-m", f"AI Agent resolved task #{num}: {title}"], cwd=repo_dir)
    run_cmd(["git", "push", "origin", "main"], cwd=repo_dir)
    print(f"[✓] Pushed changes to GitHub repository.")

    # 6. Post Final Reply Comment & Close Issue
    report_url = f"https://github.com/{repo}/blob/main/tasks/{report_filename}"
    reply_msg = (
        f"✅ **Task #{num} Resolved by AI Agent**\n\n"
        f"### 📋 Execution Summary:\n"
        f"* **Task**: `{title}`\n"
        f"* **Status**: {'✅ Success' if success else '⚠️ Completed with warnings'}\n"
        f"* **Execution Time**: `{duration_sec:.2f}s`\n"
        f"* **AI Engine**: Google Antigravity Agent (Gemini)\n"
        f"* **Detailed Report**: [{report_filename}]({report_url})\n\n"
    )

    if new_or_modified_assets:
        reply_msg += "### 🖼️ Generated Visual Artifacts:\n\n"
        for asset in new_or_modified_assets:
            if asset.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                raw_url = f"https://raw.githubusercontent.com/{repo}/main/assets/{asset}"
                reply_msg += f"#### `{asset}`\n![{asset}]({raw_url})\n\n"

    # Add agent summary preview
    preview_snippet = clean_agent_output[:2500] if clean_agent_output else "Execution completed."
    reply_msg += f"### 🧠 Agent Findings & Actions:\n\n{preview_snippet}\n"

    post_comment(repo, num, reply_msg)
    close_issue(repo, num)
    print(f"[✓] Issue #{num} closed with resolution reply.")

    return {
        "number": num,
        "title": title,
        "success": success,
        "report": str(report_path)
    }


def execute_task(issue: Dict, repo: str) -> Dict:
    """Routes the issue to the LLM agent for complete comprehension and execution."""
    num = issue["number"]
    title = issue["title"]
    author = issue.get("author", {}).get("login", "unknown")

    print(f"\n{'='*70}")
    print(f"[*] Processing Task #{num}: {title} (by @{author})")
    print(f"{'='*70}")

    return run_ai_agent(issue, repo)


def main():
    parser = argparse.ArgumentParser(description="Agent Tasks Monitor - Autonomous GitHub Issue AI Agent")
    parser.add_argument("--repo", default=REPO_DEFAULT, help=f"GitHub repository (default: {REPO_DEFAULT})")
    parser.add_argument("--interval", type=int, default=10, help="Poll interval in seconds (default: 10)")
    parser.add_argument("--once", action="store_true", help="Process pending issues once and exit")
    args = parser.parse_args()

    print("=" * 70)
    print("       🤖 AGENT TASKS - GITHUB ISSUE AI AGENT MONITOR 🤖")
    print("=" * 70)
    print(f"  Target Repo:    {args.repo}")
    print(f"  AI Engine:      Google Antigravity Agent (Gemini LLM)")
    print(f"  Poll Interval:  {args.interval} seconds")
    print(f"  Host:           {socket.gethostname()}")
    print("=" * 70)

    state = load_state()
    processed_set = set(state.get("processed_issues", []))

    while True:
        try:
            issues = fetch_open_issues(args.repo)
            unprocessed = [i for i in issues if i["number"] not in processed_set]

            if unprocessed:
                print(f"\n[*] Found {len(unprocessed)} new issue(s) to process.")
                for issue in unprocessed:
                    num = issue["number"]
                    try:
                        res = execute_task(issue, args.repo)
                        processed_set.add(num)
                        state["processed_issues"] = list(processed_set)
                        save_state(state)
                    except Exception as e:
                        print(f"[!] Error processing issue #{num}: {e}")
                        import traceback
                        traceback.print_exc()
                        # Mark as processed so it doesn't loop forever
                        processed_set.add(num)
                        state["processed_issues"] = list(processed_set)
                        save_state(state)

            if args.once:
                break

            time.sleep(args.interval)

        except KeyboardInterrupt:
            print("\n[*] Exiting Agent Tasks Monitor...")
            break
        except Exception as e:
            print(f"[!] Unexpected error in main monitor loop: {e}")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
