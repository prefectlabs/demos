"""
Backfill Script -- Trigger Historical Window Processing
========================================================

Demonstrates programmatic backfill using run_deployment(). Each
historical window gets its own flow run with full lineage and
observability. Concurrency is controlled by the work pool, not
this script.

Prerequisites:
    The flow must be served or deployed first:
        python flow.py --serve   (in another terminal)

Usage:
    # Backfill last 7 days in 6-hour windows
    python backfill.py --days 7

    # Backfill a specific date range
    python backfill.py --start 2024-01-01 --end 2024-01-07

    # Backfill with 12-hour windows
    python backfill.py --days 3 --window-hours 12

    # Dry run (show what would be triggered)
    python backfill.py --days 7 --dry-run
"""

import argparse
from datetime import datetime, timedelta

from prefect.deployments import run_deployment

DEPLOYMENT_NAME = "process-claims-window/claims-window-processor"


def generate_windows(
    start_date: datetime,
    end_date: datetime,
    window_hours: int = 6,
) -> list[dict]:
    """Generate non-overlapping windows between start and end dates."""
    windows = []
    current = start_date
    while current < end_date:
        window_end = min(current + timedelta(hours=window_hours), end_date)
        windows.append(
            {
                "window_start": current.isoformat(),
                "window_end": window_end.isoformat(),
            }
        )
        current = window_end
    return windows


def main():
    parser = argparse.ArgumentParser(
        description="Backfill claims processing for historical windows",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to backfill (default: 7)",
    )
    parser.add_argument("--start", help="Backfill start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="Backfill end date (YYYY-MM-DD)")
    parser.add_argument(
        "--window-hours",
        type=int,
        default=6,
        help="Window size in hours (default: 6)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be triggered without triggering",
    )
    args = parser.parse_args()

    if args.start and args.end:
        start = datetime.fromisoformat(args.start)
        end = datetime.fromisoformat(args.end)
    else:
        end = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=args.days)

    windows = generate_windows(start, end, args.window_hours)

    print(f"\nBackfill Plan")
    print(f"  Range: {start.date()} to {end.date()}")
    print(f"  Window size: {args.window_hours} hours")
    print(f"  Total windows: {len(windows)}")
    print(f"  Deployment: {DEPLOYMENT_NAME}")
    print()

    if args.dry_run:
        for i, w in enumerate(windows, 1):
            print(f"  [{i:>3}/{len(windows)}] {w['window_start']} -> {w['window_end']}")
        print(f"\n  Dry run complete. Remove --dry-run to trigger.")
        return

    for i, window_params in enumerate(windows, 1):
        print(
            f"  [{i:>3}/{len(windows)}] Triggering: "
            f"{window_params['window_start']} -> {window_params['window_end']}"
        )

        run_deployment(
            name=DEPLOYMENT_NAME,
            parameters=window_params,
            timeout=0,  # Fire and forget -- work pool controls concurrency
        )

    print(f"\n  Triggered {len(windows)} backfill runs.")
    print(f"  Monitor progress in the Prefect UI.")
    print(f"  Concurrency controlled by work pool limits.")


if __name__ == "__main__":
    main()
