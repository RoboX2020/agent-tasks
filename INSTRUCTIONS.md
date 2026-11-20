# Instructions & Issue Specifications 📋

This document outlines the protocols, tags, and formatting standards for remote tasks filed via GitHub Issues.

---

## 🏷️ Task Tags (Issue Titles)

Prefixing issue titles with a tag helps the agent classify and optimize task execution:

| Tag | Category | Description |
| :--- | :--- | :--- |
| `[CMD]` or `[BASH]` | Shell Execution | Run shell commands, CLI utilities, system checks |
| `[PYTHON]` | Script Execution | Run a Python script or analysis block |
| `[ROBOT]` | Physical / Sim Action | Execute Baxter moves, choreographies, arena modes, or Isaac Sim |
| `[DOC]` | Documentation | Write or edit markdown files, guides, reports |
| `[FIX]` | Bugfix / Code Edit | Modify codebase, run tests, and commit fixes |
| `[GENERAL]` | Open-ended Task | General instruction, research, or multi-step goal |

*Example Title*: `[ROBOT] Untuck Baxter and wave to camera`

---

## 💻 Issue Body Formatting

### 1. Code Blocks
Any fenced code block with `bash` or `sh` is executed in order using `bash`:
````markdown
Please check robot connectivity and untuck arms:

```bash
baxter status
baxter untuck
```
````

Any fenced code block with `python` or `py` is executed using Python 3:
````markdown
Check system memory and GPU devices:

```python
import torch
print("CUDA Available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("Device:", torch.cuda.get_device_name(0))
```
````

### 2. File Creation / Markdown Directives
To request writing a file, specify the target file path in backticks:
```markdown
Write a brief testing note in `tasks/notes.md` with current timestamp and Baxter state.
```

---

## 📊 Output Protocol

When an issue is processed:
1. **Initial Acknowledgment**:
   ```markdown
   🤖 **Agent Registered Task #12**
   * **Task**: [ROBOT] Untuck Baxter and wave to camera
   * **Started At**: 2026-11-20 16:30:00 UTC
   * **Status**: ⏳ In Progress...
   ```

2. **Resolution Artifact**:
   * The agent generates `tasks/issue-<ID>-<slug>.md` containing:
     * Full execution transcript
     * Standard output & error logs
     * Exit codes and execution timestamps
     * Modified / created files list
   * The file is committed and pushed directly to `origin/main`.

3. **Final Issue Reply & Close**:
   ```markdown
   ✅ **Task Completed: [ROBOT] Untuck Baxter and wave to camera**
   
   ### Execution Summary:
   * **Duration**: 4.2 seconds
   * **Exit Status**: Success (0)
   * **Report**: [`tasks/issue-12-untuck-baxter.md`](https://github.com/RoboX2020/agent-tasks/blob/main/tasks/issue-12-untuck-baxter.md)
   
   ```bash
   [✓] Finished move: wave
   ```
   ```
   The issue is automatically marked as closed.
