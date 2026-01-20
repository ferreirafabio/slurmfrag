"""Output formatters for slurmfrag."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO
import sys

from .collectors import NodeInfo, PartitionInfo
from .config import Config


class TerminalFormatter:
    """Format partition info for terminal display."""

    def __init__(self, config: Config | None = None, color: bool = True):
        self.config = config or Config()
        self.color = color and sys.stdout.isatty()

    def _c(self, color_attr: str, text: str) -> str:
        """Apply color if enabled."""
        if not self.color:
            return text
        color_code = getattr(self.config, color_attr, "")
        reset = self.config.color_reset
        return f"{color_code}{text}{reset}"

    def format_header(self, partition: str, resource_type: str) -> str:
        """Format the report header."""
        lines = [
            "",
            "=" * 50,
            f"  {resource_type.upper()} Fragmentation Report",
            f"  Partition: {partition}",
            f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 50,
            "",
        ]
        return "\n".join(lines)

    def format_node_table(self, info: PartitionInfo, resource_type: str) -> str:
        """Format the per-node status table."""
        lines = [
            "Per-Node Status:",
            "-" * 70,
        ]

        header = f"{'NODE':<20} {'USED':>8} {'TOTAL':>8} {'USE%':>7}  FRAGMENTATION"
        lines.append(header)
        lines.append("")

        for node in info.nodes:
            total, used, free = node.get_resource(resource_type)
            pct = (used / total * 100) if total > 0 else 0

            # Create scaled visual representation (20 chars wide)
            visual = self._create_visual(used, total, width=20)

            line = f"{node.hostname:<20} {used:>8} {total:>8} {pct:>6.1f}%  [{visual}]"
            lines.append(line)

        return "\n".join(lines)

    def _create_visual(self, used: int, total: int, width: int = 20) -> str:
        """Create scaled visual bar representation.

        Args:
            used: Number of used resources
            total: Total resources
            width: Width of the bar in characters
        """
        if total == 0:
            return self.config.free_symbol * width

        used_width = round(used / total * width)
        free_width = width - used_width

        used_sym = self.config.used_symbol
        free_sym = self.config.free_symbol
        return (used_sym * used_width) + (free_sym * free_width)

    def format_summary(self, info: PartitionInfo, resource_type: str) -> str:
        """Format the summary section."""
        total, used, free = info.get_resource_totals(resource_type)
        utilization = (used / total * 100) if total > 0 else 0

        node_states = info.nodes_by_state()

        lines = [
            "",
            "=" * 50,
            "  Summary",
            "=" * 50,
            "",
        ]

        if total > 0:
            resource_name = resource_type.upper()
            if resource_type in ("mem", "memory"):
                resource_name = "Memory (GB)"

            lines.extend([
                f"Total {resource_name}:     {total}",
                f"Used {resource_name}:      {used}",
                f"Free {resource_name}:      {free}",
                f"Utilization:    {utilization:.1f}%",
            ])
        else:
            lines.append(f"No {resource_type} information available for this partition.")

        lines.extend([
            "",
            "Node States:",
            f"  Idle (all free):      {node_states.get('idle', 0)}",
            f"  Mixed (fragmented):   {node_states.get('mixed', 0)}",
            f"  Allocated (all used): {node_states.get('allocated', 0)}",
            f"  Drain:                {node_states.get('drain', 0)}",
            "",
        ])

        return "\n".join(lines)

    def format_largest_blocks(self, info: PartitionInfo, resource_type: str, limit: int = 10) -> str:
        """Format the largest contiguous free blocks section."""
        blocks = info.largest_free_blocks(resource_type, limit)

        resource_name = resource_type.upper()
        if resource_type in ("mem", "memory"):
            resource_name = "Memory (GB)"

        lines = [
            "=" * 50,
            f"  Largest Contiguous {resource_name} Blocks",
            "=" * 50,
            "",
            "Largest single-node allocations available:",
            "",
        ]

        if blocks:
            for hostname, count in blocks:
                lines.append(f"  {hostname}: {count} {resource_name} free")
        else:
            lines.append("  No free resources available")

        lines.extend([
            "",
            f"Legend: {self.config.used_symbol} = Used, {self.config.free_symbol} = Free",
            "",
        ])

        return "\n".join(lines)

    def format_full_report(self, info: PartitionInfo, resource_type: str) -> str:
        """Format a complete report for a single resource type."""
        sections = [
            self.format_header(info.name, resource_type),
            self.format_node_table(info, resource_type),
            self.format_summary(info, resource_type),
            self.format_largest_blocks(info, resource_type),
        ]
        return "\n".join(sections)

    def format_combined_report(self, info: PartitionInfo) -> str:
        """Format a combined report with all resource types (GPU, CPU, Memory)."""
        sections = [
            self._format_combined_header(info.name),
            self._format_queue_status(info),
        ]

        for resource_type in ["gpu", "cpu", "mem"]:
            sections.append(self._format_resource_section(info, resource_type))

        sections.append("")
        return "\n".join(sections)

    def _format_combined_header(self, partition: str) -> str:
        """Format header for combined report."""
        lines = [
            "",
            "=" * 60,
            "  SLURM Fragmentation Report",
            f"  Partition: {partition}",
            f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
        ]
        return "\n".join(lines)

    def _format_queue_status(self, info: PartitionInfo) -> str:
        """Format queue status section."""
        q = info.queue

        # Format memory nicely
        if q.pending_memory_gb >= 1024:
            mem_str = f"{q.pending_memory_gb / 1024:.1f} TB"
        else:
            mem_str = f"{q.pending_memory_gb:,} GB"

        lines = [
            "",
            "-" * 60,
            "  Queue Status",
            "-" * 60,
            f"  Running: {q.running_jobs} jobs    Pending: {q.pending_jobs} jobs",
            "",
            f"  Pending requests: {q.pending_gpus} GPUs | {q.pending_cpus:,} CPUs | {mem_str}",
        ]
        return "\n".join(lines)

    def _format_resource_section(self, info: PartitionInfo, resource_type: str) -> str:
        """Format a single resource section for the combined report."""
        resource_name = resource_type.upper()
        if resource_type in ("mem", "memory"):
            resource_name = "Memory (GB)"

        # Get totals for summary line
        total, used, free = info.get_resource_totals(resource_type)
        utilization = (used / total * 100) if total > 0 else 0

        lines = [
            "",
            "-" * 60,
            f"  {resource_name}: {used}/{total} used ({utilization:.1f}%)",
            "-" * 60,
            "",
            f"{'NODE':<20} {'USED':>8} {'TOTAL':>8} {'USE%':>7}  FRAGMENTATION",
        ]

        for node in info.nodes:
            node_total, node_used, node_free = node.get_resource(resource_type)
            pct = (node_used / node_total * 100) if node_total > 0 else 0
            visual = self._create_visual(node_used, node_total, width=20)

            line = f"{node.hostname:<20} {node_used:>8} {node_total:>8} {pct:>6.1f}%  [{visual}]"
            lines.append(line)

        return "\n".join(lines)


class JSONFormatter:
    """Format partition info as JSON."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def format(self, info: PartitionInfo, pretty: bool = True) -> str:
        """Format partition info as JSON string."""
        data = info.to_dict()
        if pretty:
            return json.dumps(data, indent=2, default=str)
        return json.dumps(data, default=str)

    def write_log(
        self,
        info: PartitionInfo,
        output_dir: str | Path | None = None,
    ) -> Path:
        """Write JSON log to file.

        File naming: {partition}_{timestamp}.json
        """
        if output_dir is None:
            output_dir = Path(self.config.logging.output_dir)
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = info.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{info.name}_{timestamp}.json"
        filepath = output_dir / filename

        with open(filepath, "w") as f:
            f.write(self.format(info, pretty=True))

        return filepath


class LogDaemon:
    """Daemon for periodic JSON logging."""

    def __init__(
        self,
        collector: Any,  # SlurmCollector
        partition: str,
        config: Config | None = None,
    ):
        self.collector = collector
        self.partition = partition
        self.config = config or Config()
        self.formatter = JSONFormatter(config)
        self._stop_event: Any = None  # threading.Event

    def run_once(self) -> Path:
        """Collect and log once."""
        info = self.collector.collect_partition(self.partition)
        return self.formatter.write_log(info)

    def run(self, interval_minutes: int | None = None) -> None:
        """Run periodic logging.

        Args:
            interval_minutes: Override config interval
        """
        import threading
        import signal

        interval = interval_minutes or self.config.logging.interval_minutes
        interval_seconds = interval * 60

        self._stop_event = threading.Event()

        def handle_signal(signum: int, frame: Any) -> None:
            print("\nStopping log daemon...")
            self._stop_event.set()

        # Store original handlers
        original_sigint = signal.signal(signal.SIGINT, handle_signal)
        original_sigterm = signal.signal(signal.SIGTERM, handle_signal)

        print(f"Starting log daemon for partition '{self.partition}'")
        print(f"Logging every {interval} minutes to: {self.config.logging.output_dir}")
        print("Press Ctrl+C to stop\n")

        try:
            while not self._stop_event.is_set():
                try:
                    filepath = self.run_once()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Logged to: {filepath}")
                except Exception as e:
                    print(f"Error during logging: {e}")

                # Wait with ability to interrupt
                self._stop_event.wait(timeout=interval_seconds)
        finally:
            # Restore original handlers
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)

        print("Log daemon stopped.")
