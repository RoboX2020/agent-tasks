# Task Report #3: [PYTHON] Inspect PyTorch CUDA GPU properties

* **Issue**: [#3](https://github.com/RoboX2020/agent-tasks/issues/3)
* **Author**: @RoboX2020
* **Started**: 2026-11-20 23:31:18 UTC
* **Completed**: 2026-11-20 23:31:20 UTC
* **Duration**: 1.24 seconds
* **Status**: ❌ Failed

---

## Task Instructions

Check PyTorch CUDA device name and memory allocation in Isaac environment.

```python
import torch
print("CUDA Available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU Model:", torch.cuda.get_device_name(0))
    print("Allocated Memory:", torch.cuda.memory_allocated(0))
```

---

## Execution Logs

### Block 1 (`python`)

**Input:**
```python
import torch
print("CUDA Available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU Model:", torch.cuda.get_device_name(0))
    print("Allocated Memory:", torch.cuda.memory_allocated(0))
```

**Exit Code:** `1`

**Stderr:**
```text
File "<string>", line 1
    import torch\nprint("CUDA Available:", torch.cuda.is_available())\nif torch.cuda.is_available():\n    print("GPU Model:", torch.cuda.get_device_name(0))\n    print("Allocated Memory:", torch.cuda.memory_allocated(0))
                 ^
SyntaxError: unexpected character after line continuation character
```

