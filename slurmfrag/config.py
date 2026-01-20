"""Configuration handling for sfrag."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class GresConfig:
    """Configuration for parsing GRES (Generic Resources)."""

    # Regex pattern to extract resource count from gres string
    # Default handles: gpu:8, gpu:H200:8, gpu:nvidia:a100:4
    pattern: str = r"gpu[^:]*:(\d+)"
    # Display name for this resource
    display_name: str = "GPU"
    # Symbols for visualization
    used_symbol: str = "\u2588"  # █
    free_symbol: str = "\u2591"  # ░


@dataclass
class PartitionConfig:
    """Configuration for a specific partition."""

    name: str
    # Resource type to analyze: gpu, cpu, memory
    resource_type: str = "gpu"
    # Custom gres parsing config (optional)
    gres: GresConfig | None = None


@dataclass
class LoggingConfig:
    """Configuration for JSON logging."""

    enabled: bool = False
    # Directory to write JSON logs
    output_dir: str = "./sfrag_logs"
    # Interval in minutes between log dumps
    interval_minutes: int = 5
    # Keep logs for this many days (0 = forever)
    retention_days: int = 7


@dataclass
class Config:
    """Main configuration for sfrag."""

    # Default resource type when not specified
    default_resource: str = "gpu"

    # GRES patterns for different resource types
    gres_patterns: dict[str, GresConfig] = field(default_factory=dict)

    # Partition-specific overrides
    partitions: dict[str, PartitionConfig] = field(default_factory=dict)

    # JSON logging configuration
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Visual settings
    used_symbol: str = "\u2588"  # █
    free_symbol: str = "\u2591"  # ░

    # Colors (ANSI codes, empty string to disable)
    color_idle: str = "\033[32m"  # Green
    color_mixed: str = "\033[33m"  # Yellow
    color_allocated: str = "\033[31m"  # Red
    color_drain: str = "\033[90m"  # Gray
    color_reset: str = "\033[0m"

    def __post_init__(self) -> None:
        """Set up default GRES patterns."""
        if not self.gres_patterns:
            self.gres_patterns = {
                "gpu": GresConfig(
                    pattern=r"gpu[^:]*:(\d+)",
                    display_name="GPU",
                ),
                "cpu": GresConfig(
                    pattern=r"cpu[^:]*:(\d+)",
                    display_name="CPU",
                ),
                "mem": GresConfig(
                    pattern=r"mem[^:]*:(\d+)",
                    display_name="Memory (GB)",
                ),
            }

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> Config:
        """Load configuration from YAML file.

        Searches in order:
        1. Provided path
        2. ./sfrag.yaml
        3. ~/.config/sfrag/config.yaml
        4. /etc/sfrag/config.yaml
        5. Default configuration
        """
        search_paths = [
            config_path,
            Path("./sfrag.yaml"),
            Path("./sfrag.yml"),
            Path.home() / ".config" / "sfrag" / "config.yaml",
            Path("/etc/sfrag/config.yaml"),
        ]

        for path in search_paths:
            if path is None:
                continue
            path = Path(path)
            if path.exists():
                return cls._load_from_file(path)

        # Return default config
        return cls()

    @classmethod
    def _load_from_file(cls, path: Path) -> Config:
        """Load configuration from a specific file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        # Parse gres patterns
        gres_patterns = {}
        for name, gres_data in data.get("gres_patterns", {}).items():
            gres_patterns[name] = GresConfig(**gres_data)

        # Parse partitions
        partitions = {}
        for name, part_data in data.get("partitions", {}).items():
            if "gres" in part_data and isinstance(part_data["gres"], dict):
                part_data["gres"] = GresConfig(**part_data["gres"])
            partitions[name] = PartitionConfig(name=name, **part_data)

        # Parse logging
        logging_data = data.get("logging", {})
        logging_config = LoggingConfig(**logging_data) if logging_data else LoggingConfig()

        return cls(
            default_resource=data.get("default_resource", "gpu"),
            gres_patterns=gres_patterns if gres_patterns else {},
            partitions=partitions,
            logging=logging_config,
            used_symbol=data.get("used_symbol", "\u2588"),
            free_symbol=data.get("free_symbol", "\u2591"),
            color_idle=data.get("color_idle", "\033[32m"),
            color_mixed=data.get("color_mixed", "\033[33m"),
            color_allocated=data.get("color_allocated", "\033[31m"),
            color_drain=data.get("color_drain", "\033[90m"),
            color_reset=data.get("color_reset", "\033[0m"),
        )

    def get_gres_pattern(self, resource_type: str) -> GresConfig:
        """Get GRES config for a resource type."""
        if resource_type in self.gres_patterns:
            return self.gres_patterns[resource_type]
        # Return default GPU pattern
        return GresConfig()

    def get_partition_config(self, partition: str) -> PartitionConfig | None:
        """Get partition-specific configuration."""
        return self.partitions.get(partition)
