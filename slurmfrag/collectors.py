"""Data collectors for SLURM cluster information."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .config import Config, GresConfig


@dataclass
class NodeInfo:
    """Information about a single node."""

    hostname: str
    state: str
    total_gpus: int = 0
    used_gpus: int = 0
    total_cpus: int = 0
    used_cpus: int = 0
    total_memory_gb: int = 0
    used_memory_gb: int = 0
    # Raw gres strings for custom parsing
    gres_raw: str = ""
    gres_used_raw: str = ""

    @property
    def free_gpus(self) -> int:
        return self.total_gpus - self.used_gpus

    @property
    def free_cpus(self) -> int:
        return self.total_cpus - self.used_cpus

    @property
    def free_memory_gb(self) -> int:
        return self.total_memory_gb - self.used_memory_gb

    @property
    def state_normalized(self) -> str:
        """Normalize state to simple categories."""
        state_lower = self.state.lower()
        if "idle" in state_lower:
            return "idle"
        elif "mix" in state_lower:
            return "mixed"
        elif "alloc" in state_lower:
            return "allocated"
        elif "drain" in state_lower:
            return "drain"
        elif "down" in state_lower:
            return "down"
        else:
            return self.state

    def get_resource(self, resource_type: str) -> tuple[int, int, int]:
        """Get (total, used, free) for a resource type."""
        if resource_type == "gpu":
            return self.total_gpus, self.used_gpus, self.free_gpus
        elif resource_type == "cpu":
            return self.total_cpus, self.used_cpus, self.free_cpus
        elif resource_type in ("mem", "memory"):
            return self.total_memory_gb, self.used_memory_gb, self.free_memory_gb
        else:
            return 0, 0, 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "hostname": self.hostname,
            "state": self.state,
            "state_normalized": self.state_normalized,
            "gpu": {
                "total": self.total_gpus,
                "used": self.used_gpus,
                "free": self.free_gpus,
            },
            "cpu": {
                "total": self.total_cpus,
                "used": self.used_cpus,
                "free": self.free_cpus,
            },
            "memory_gb": {
                "total": self.total_memory_gb,
                "used": self.used_memory_gb,
                "free": self.free_memory_gb,
            },
        }


@dataclass
class QueueInfo:
    """Information about the job queue for a partition."""

    running_jobs: int = 0
    pending_jobs: int = 0
    pending_gpus: int = 0
    pending_cpus: int = 0
    pending_memory_gb: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "running_jobs": self.running_jobs,
            "pending_jobs": self.pending_jobs,
            "pending_resources": {
                "gpus": self.pending_gpus,
                "cpus": self.pending_cpus,
                "memory_gb": self.pending_memory_gb,
            },
        }


@dataclass
class PartitionInfo:
    """Information about a partition."""

    name: str
    nodes: list[NodeInfo] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    queue: QueueInfo = field(default_factory=QueueInfo)

    @property
    def total_gpus(self) -> int:
        return sum(n.total_gpus for n in self.nodes)

    @property
    def used_gpus(self) -> int:
        return sum(n.used_gpus for n in self.nodes)

    @property
    def free_gpus(self) -> int:
        return sum(n.free_gpus for n in self.nodes)

    @property
    def total_cpus(self) -> int:
        return sum(n.total_cpus for n in self.nodes)

    @property
    def used_cpus(self) -> int:
        return sum(n.used_cpus for n in self.nodes)

    @property
    def free_cpus(self) -> int:
        return sum(n.free_cpus for n in self.nodes)

    @property
    def total_memory_gb(self) -> int:
        return sum(n.total_memory_gb for n in self.nodes)

    @property
    def used_memory_gb(self) -> int:
        return sum(n.used_memory_gb for n in self.nodes)

    @property
    def free_memory_gb(self) -> int:
        return sum(n.free_memory_gb for n in self.nodes)

    def get_resource_totals(self, resource_type: str) -> tuple[int, int, int]:
        """Get (total, used, free) for a resource type across all nodes."""
        if resource_type == "gpu":
            return self.total_gpus, self.used_gpus, self.free_gpus
        elif resource_type == "cpu":
            return self.total_cpus, self.used_cpus, self.free_cpus
        elif resource_type in ("mem", "memory"):
            return self.total_memory_gb, self.used_memory_gb, self.free_memory_gb
        else:
            return 0, 0, 0

    def nodes_by_state(self) -> dict[str, int]:
        """Count nodes by state."""
        counts: dict[str, int] = {}
        for node in self.nodes:
            state = node.state_normalized
            counts[state] = counts.get(state, 0) + 1
        return counts

    def largest_free_blocks(self, resource_type: str, limit: int = 10) -> list[tuple[str, int]]:
        """Get nodes with largest contiguous free blocks of a resource."""
        blocks = []
        for node in self.nodes:
            total, used, free = node.get_resource(resource_type)
            if free > 0:
                blocks.append((node.hostname, free))
        return sorted(blocks, key=lambda x: x[1], reverse=True)[:limit]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "partition": self.name,
            "timestamp": self.timestamp.isoformat(),
            "queue": self.queue.to_dict(),
            "summary": {
                "gpu": {
                    "total": self.total_gpus,
                    "used": self.used_gpus,
                    "free": self.free_gpus,
                    "utilization_pct": round(self.used_gpus / self.total_gpus * 100, 1)
                    if self.total_gpus > 0
                    else 0,
                },
                "cpu": {
                    "total": self.total_cpus,
                    "used": self.used_cpus,
                    "free": self.free_cpus,
                    "utilization_pct": round(self.used_cpus / self.total_cpus * 100, 1)
                    if self.total_cpus > 0
                    else 0,
                },
                "memory_gb": {
                    "total": self.total_memory_gb,
                    "used": self.used_memory_gb,
                    "free": self.free_memory_gb,
                    "utilization_pct": round(self.used_memory_gb / self.total_memory_gb * 100, 1)
                    if self.total_memory_gb > 0
                    else 0,
                },
                "nodes_by_state": self.nodes_by_state(),
            },
            "nodes": [n.to_dict() for n in self.nodes],
        }


class SlurmCollector:
    """Collector for SLURM cluster information."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def get_partitions(self) -> list[str]:
        """Get list of all partitions."""
        try:
            result = subprocess.run(
                ["sinfo", "-o", "%P", "--noheader"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return []

            partitions = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    # Remove asterisk from default partition
                    partitions.append(line.strip().rstrip("*"))
            return sorted(set(partitions))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    def get_gpu_partitions(self) -> list[str]:
        """Get list of partitions with GPU resources."""
        try:
            result = subprocess.run(
                ["sinfo", "-o", "%P %G", "--noheader"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return []

            partitions = []
            for line in result.stdout.strip().split("\n"):
                if line and "gpu" in line.lower():
                    parts = line.split()
                    if parts:
                        partitions.append(parts[0].rstrip("*"))
            return sorted(set(partitions))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    def collect_partition(self, partition: str, resource_type: str = "gpu") -> PartitionInfo:
        """Collect information about a specific partition."""
        nodes = self._collect_nodes(partition, resource_type)
        queue = self._collect_queue_info(partition)
        return PartitionInfo(name=partition, nodes=nodes, queue=queue, timestamp=datetime.now())

    def _collect_nodes(self, partition: str, resource_type: str) -> list[NodeInfo]:
        """Collect node information from sinfo."""
        # Get node info with all relevant fields
        # Format: NodeHost StateLong CPUsState Memory AllocMem Gres GresUsed
        try:
            result = subprocess.run(
                [
                    "sinfo",
                    "-p",
                    partition,
                    "-N",
                    "--noheader",
                    "-O",
                    "NodeHost,StateLong,CPUsState,Memory,AllocMem,Gres,GresUsed",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return []

            nodes = []
            seen_hosts = set()

            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue

                node = self._parse_node_line(line, resource_type)
                if node and node.hostname not in seen_hosts:
                    nodes.append(node)
                    seen_hosts.add(node.hostname)

            return nodes
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    def _parse_node_line(self, line: str, resource_type: str) -> NodeInfo | None:
        """Parse a single line of sinfo output."""
        # Split by whitespace, but be careful with empty fields
        parts = line.split()
        if len(parts) < 5:
            return None

        hostname = parts[0]
        state = parts[1]

        # Parse CPUsState (format: allocated/idle/other/total)
        cpus_state = parts[2] if len(parts) > 2 else "0/0/0/0"
        cpu_parts = cpus_state.split("/")
        if len(cpu_parts) >= 4:
            used_cpus = int(cpu_parts[0]) if cpu_parts[0].isdigit() else 0
            total_cpus = int(cpu_parts[3]) if cpu_parts[3].isdigit() else 0
        else:
            used_cpus = 0
            total_cpus = 0

        # Parse Memory (in MB)
        memory_str = parts[3] if len(parts) > 3 else "0"
        total_memory_mb = self._parse_memory(memory_str)

        # Parse AllocMem (in MB)
        alloc_mem_str = parts[4] if len(parts) > 4 else "0"
        used_memory_mb = self._parse_memory(alloc_mem_str)

        # Parse Gres
        gres = parts[5] if len(parts) > 5 else ""
        gres_used = parts[6] if len(parts) > 6 else ""

        # Extract GPU counts
        total_gpus = self._extract_gpu_count(gres)
        used_gpus = self._extract_gpu_count(gres_used)

        return NodeInfo(
            hostname=hostname,
            state=state,
            total_gpus=total_gpus,
            used_gpus=used_gpus,
            total_cpus=total_cpus,
            used_cpus=used_cpus,
            total_memory_gb=total_memory_mb // 1024,
            used_memory_gb=used_memory_mb // 1024,
            gres_raw=gres,
            gres_used_raw=gres_used,
        )

    def _parse_memory(self, mem_str: str) -> int:
        """Parse memory string to MB."""
        if not mem_str or mem_str == "(null)":
            return 0

        # Remove any non-numeric suffix and parse
        mem_str = mem_str.strip()
        multiplier = 1

        if mem_str.endswith("G"):
            multiplier = 1024
            mem_str = mem_str[:-1]
        elif mem_str.endswith("T"):
            multiplier = 1024 * 1024
            mem_str = mem_str[:-1]
        elif mem_str.endswith("M"):
            mem_str = mem_str[:-1]

        try:
            return int(float(mem_str)) * multiplier
        except ValueError:
            return 0

    def _extract_gpu_count(self, gres_str: str) -> int:
        """Extract GPU count from gres string."""
        if not gres_str or gres_str == "(null)":
            return 0

        # Get pattern from config
        gres_config = self.config.get_gres_pattern("gpu")

        # Try to match the pattern
        match = re.search(gres_config.pattern, gres_str)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass

        # Fallback: try common patterns
        patterns = [
            r"gres/gpu:(\d+)",  # gres/gpu:8 (squeue format)
            r"gpu:(\d+)",  # gpu:8
            r"gpu:[^:]+:(\d+)",  # gpu:H200:8
            r"gpu:[^:]+:[^:]+:(\d+)",  # gpu:nvidia:a100:4
        ]

        for pattern in patterns:
            match = re.search(pattern, gres_str)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue

        return 0

    def _extract_resource_count(self, gres_str: str, resource_type: str) -> int:
        """Extract resource count from gres string using config pattern."""
        if not gres_str or gres_str == "(null)":
            return 0

        gres_config = self.config.get_gres_pattern(resource_type)
        match = re.search(gres_config.pattern, gres_str)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass
        return 0

    def _collect_queue_info(self, partition: str) -> QueueInfo:
        """Collect job queue information for a partition."""
        queue = QueueInfo()

        # Count running jobs
        try:
            result = subprocess.run(
                ["squeue", "-p", partition, "-h", "-t", "R", "-o", "%i"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                queue.running_jobs = len([l for l in result.stdout.strip().split("\n") if l.strip()])
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Count pending jobs and their resource requests
        # Use --Format with tres field to get full GRES including TresPerJob
        # Use -r to expand job arrays into individual tasks
        # Only count jobs waiting on Resources/Priority (not JobArrayTaskLimit, Dependency, etc.)
        try:
            result = subprocess.run(
                ["squeue", "-p", partition, "-h", "-t", "PD", "-r",
                 "--Format=tres:100,reason:30"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line.strip():
                        continue

                    # Format is fixed-width: tres (100 chars), reason (30 chars)
                    tres = line[:100].strip()
                    reason = line[100:].strip()

                    queue.pending_jobs += 1

                    # Only count resource requests for jobs actually waiting on resources
                    # (not JobArrayTaskLimit, Dependency, etc.)
                    if "Resources" in reason or "Priority" in reason:
                        # Parse GRES for GPUs from tres field (format: gres/gpu=N)
                        gpu_match = re.search(r"gres/gpu=(\d+)", tres)
                        if gpu_match:
                            queue.pending_gpus += int(gpu_match.group(1))

                        # Parse CPUs from tres field (format: cpu=N)
                        cpu_match = re.search(r"cpu=(\d+)", tres)
                        if cpu_match:
                            queue.pending_cpus += int(cpu_match.group(1))

                        # Parse Memory from tres field (format: mem=NG or mem=NM or mem=NT)
                        mem_match = re.search(r"mem=(\d+)([GMTgmt])?", tres)
                        if mem_match:
                            mem_val = int(mem_match.group(1))
                            unit = (mem_match.group(2) or "M").upper()
                            if unit == "G":
                                queue.pending_memory_gb += mem_val
                            elif unit == "T":
                                queue.pending_memory_gb += mem_val * 1024
                            elif unit == "M":
                                queue.pending_memory_gb += mem_val // 1024
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return queue
