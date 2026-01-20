[![PyPI Downloads](https://static.pepy.tech/personalized-badge/slurmfrag?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=BRIGHTGREEN&left_text=downloads)](https://pepy.tech/projects/slurmfrag)

# slurmfrag 🧩

```
┌─────────────────────────────────────────────────────────────────────────┐
│  GPU: 25/32 used (78.1%)                                                │
├─────────────────────────────────────────────────────────────────────────┤
│  NODE          USED    TOTAL    USE%   FRAGMENTATION                    │
│  gpunode01        7        8   87.5%   [██████████████████░░]           │
│  gpunode02        8        8  100.0%   [████████████████████]           │
│  gpunode03        4        8   50.0%   [██████████░░░░░░░░░░]           │
├─────────────────────────────────────────────────────────────────────────┤
│  CPU: 374/1536 used (24.3%)                                             │
├─────────────────────────────────────────────────────────────────────────┤
│  gpunode01      124      384   32.3%   [██████░░░░░░░░░░░░░░]           │
│  gpunode02       98      384   25.5%   [█████░░░░░░░░░░░░░░░]           │
│  gpunode03      108      384   28.1%   [██████░░░░░░░░░░░░░░]           │
├─────────────────────────────────────────────────────────────────────────┤
│  Memory: 4.3/6.0 TB used (71.5%)                                        │
├─────────────────────────────────────────────────────────────────────────┤
│  gpunode01     1091     1500   72.7%   [███████████████░░░░░]           │
│  gpunode02     1070     1500   71.3%   [██████████████░░░░░░]           │
│  gpunode03     1074     1500   71.6%   [██████████████░░░░░░]           │
└─────────────────────────────────────────────────────────────────────────┘
```

Visualize SLURM cluster fragmentation — GPU, CPU, and memory usage per node, plus queue depth and pending requests. Created with the help of Claude Code (Opus 4.5).

## Features

- **All-in-one** — GPU, CPU, memory fragmentation per node in a single view
- **Queue status** — see pending jobs and total resource requests waiting
- **JSON export** — for automation and historical analysis
- **Logging daemon** — run `slurmfrag --log` to periodically capture JSON snapshots for trend analysis
- **Configurable** — YAML config for cluster-specific GRES patterns

## Quick start

**From PyPI:**
```bash
pip install slurmfrag
slurmfrag
```

**From source:**
```bash
git clone https://github.com/ferreirafabio/slurmfrag
cd slurmfrag
python -m slurmfrag
```

### Usage

```bash
slurmfrag                        # interactive partition picker
slurmfrag -p gpu-partition       # direct analysis
slurmfrag -p gpu-partition --json
slurmfrag --log                  # logging daemon mode
```

## Config

Optional `~/.config/slurmfrag/config.yaml`:

```yaml
gres_patterns:
  gpu:
    pattern: "gpu[^:]*:(\\d+)"  # adjust for your cluster

logging:
  output_dir: "./slurmfrag_logs"
  interval_minutes: 5
```

## Requirements

- Python 3.8+
- SLURM (`sinfo`, `squeue` commands)
- PyYAML

## License

Apache-2.0
