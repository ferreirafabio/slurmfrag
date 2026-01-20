"""Command-line interface for slurmfrag."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .collectors import SlurmCollector
from .config import Config
from .formatters import TerminalFormatter, JSONFormatter, LogDaemon


def select_from_menu(options: list[str], prompt: str = "Select an option") -> str | None:
    """Display an interactive menu and get user selection.

    Uses fzf if available, otherwise falls back to numbered menu.
    """
    import shutil
    import subprocess

    if not options:
        print("No options available.")
        return None

    # Try fzf first
    if shutil.which("fzf"):
        try:
            result = subprocess.run(
                ["fzf", "--prompt", f"{prompt}: ", "--height", "~50%", "--reverse"],
                input="\n".join(options),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        except Exception:
            pass  # Fall through to numbered menu

    # Fallback: numbered menu
    print(f"\n{prompt}:")
    print("-" * 40)
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")
    print(f"  q. Quit")
    print()

    while True:
        try:
            choice = input("Enter number (or 'q' to quit): ").strip().lower()
            if choice == "q":
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
            print("Invalid selection. Try again.")
        except ValueError:
            print("Please enter a number or 'q'.")
        except (EOFError, KeyboardInterrupt):
            print()
            return None


def main_interactive(config: Config) -> None:
    """Run the main interactive mode - select partition, show all resources."""
    collector = SlurmCollector(config)

    print("\n" + "=" * 50)
    print("  slurmfrag - SLURM Fragmentation Analyzer")
    print("=" * 50)

    # Get all partitions (prefer GPU partitions if available)
    partitions = collector.get_gpu_partitions()
    if not partitions:
        partitions = collector.get_partitions()

    if not partitions:
        print("Error: No partitions found. Is SLURM available?")
        return

    partition = select_from_menu(partitions, "Select partition")
    if partition is None:
        print("Goodbye!")
        return

    # Show full report with all resources
    run_full_report(collector, partition, config)


def run_full_report(collector: SlurmCollector, partition: str, config: Config) -> None:
    """Run and display a full report with GPU, CPU, and memory."""
    print(f"\nCollecting data for partition '{partition}'...")

    info = collector.collect_partition(partition)
    formatter = TerminalFormatter(config)

    # Show combined report with all resource types
    print(formatter.format_combined_report(info))


def logging_menu(config: Config) -> None:
    """Run the logging menu."""
    collector = SlurmCollector(config)

    while True:
        print("\n" + "=" * 50)
        print("  slurmfrag - JSON Logging Mode")
        print("=" * 50)

        actions = [
            "JSON output (single snapshot)",
            "Start JSON logging daemon",
            "Back",
        ]

        action = select_from_menu(actions, "Select action")

        if action is None:  # User pressed 'q' to quit
            print("Goodbye!")
            break

        if action == "Back":
            continue  # Go back to menu

        # Get partitions
        partitions = collector.get_gpu_partitions()
        if not partitions:
            partitions = collector.get_partitions()

        if not partitions:
            print("Error: No partitions found. Is SLURM available?")
            continue

        partition = select_from_menu(partitions, "Select partition")
        if partition is None:
            continue

        if "single snapshot" in action:
            run_json_output(collector, partition, config)
        elif "logging daemon" in action:
            run_log_daemon(collector, partition, config)


def run_json_output(collector: SlurmCollector, partition: str, config: Config) -> None:
    """Output JSON snapshot."""
    info = collector.collect_partition(partition)
    formatter = JSONFormatter(config)

    print("\nJSON Output:")
    print("-" * 40)
    print(formatter.format(info))

    # Ask if user wants to save
    try:
        save = input("\nSave to file? (y/N): ").strip().lower()
        if save == "y":
            filepath = formatter.write_log(info)
            print(f"Saved to: {filepath}")
    except (EOFError, KeyboardInterrupt):
        print()


def run_log_daemon(collector: SlurmCollector, partition: str, config: Config) -> None:
    """Run the JSON logging daemon."""
    # Get interval
    default_interval = config.logging.interval_minutes
    try:
        interval_str = input(f"Log interval in minutes [{default_interval}]: ").strip()
        interval = int(interval_str) if interval_str else default_interval
    except (ValueError, EOFError, KeyboardInterrupt):
        interval = default_interval

    daemon = LogDaemon(collector, partition, config=config)
    daemon.run(interval)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="slurmfrag",
        description="SLURM Fragmentation Analyzer - Visualize cluster resource fragmentation",
    )

    parser.add_argument(
        "-p", "--partition",
        help="Partition to analyze (skips partition selection menu)",
    )

    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="Path to configuration file",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of terminal format",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    parser.add_argument(
        "--log",
        action="store_true",
        help="Enter JSON logging mode (interactive menu for snapshots and daemon)",
    )

    parser.add_argument(
        "--log-interval",
        type=int,
        default=5,
        help="Logging interval in minutes for daemon (default: 5)",
    )

    parser.add_argument(
        "--log-dir",
        type=Path,
        help="Directory for JSON logs",
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Load configuration
    config = Config.load(args.config)

    # Override config with CLI args
    if args.log_dir:
        config.logging.output_dir = str(args.log_dir)

    collector = SlurmCollector(config)

    # Logging mode
    if args.log:
        if args.partition:
            # Direct daemon mode with partition
            daemon = LogDaemon(collector, args.partition, config=config)
            daemon.run(args.log_interval)
        else:
            # Interactive logging menu
            logging_menu(config)
        return 0

    # If partition provided, run non-interactive report
    if args.partition:
        if args.json:
            info = collector.collect_partition(args.partition)
            formatter = JSONFormatter(config)
            print(formatter.format(info))
        else:
            # Show all resources for the partition
            run_full_report(collector, args.partition, config)
        return 0

    # Default: Interactive mode - select partition, show all resources
    main_interactive(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
