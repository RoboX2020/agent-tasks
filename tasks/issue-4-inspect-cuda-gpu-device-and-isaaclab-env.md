# Task Report #4: [PYTHON] Inspect CUDA GPU device and IsaacLab environment

* **Issue**: [#4](https://github.com/RoboX2020/agent-tasks/issues/4)
* **Author**: @RoboX2020
* **Started**: 2026-11-20 23:32:18 UTC
* **Completed**: 2026-11-20 23:32:21 UTC
* **Duration**: 3.46 seconds
* **Status**: ✅ Success

---

## Task Instructions

Verify PyTorch CUDA device name and memory in IsaacLab environment.

```python
import torch
print("CUDA Available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU Model:", torch.cuda.get_device_name(0))
    print("Device Count:", torch.cuda.device_count())
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
    print("Device Count:", torch.cuda.device_count())
```

**Exit Code:** `0`

**Stdout:**
```text
CUDA Available: True
GPU Model: NVIDIA GB10
Device Count: 1
```

