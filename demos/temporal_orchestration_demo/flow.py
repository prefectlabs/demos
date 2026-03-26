"""
Temporal Orchestration Demo -- Claims Window Processor
======================================================

Demonstrates Prefect's temporal orchestration capabilities for customer
evaluations. Each task maps to common requirements around data processing
windows, completeness tracking, and idempotent reprocessing.

Features demonstrated:
    - Flow parameters for data processing windows (not system clock)
    - Flow run name templating for window visibility
    - Task caching with INPUTS policy for idempotent reprocessing
    - Result persistence for durable cached outputs
    - Transactions with rollback hooks for atomic writes
    - Variables for completeness boundary tracking
    - Custom events for downstream automation triggers

Usage:
    # Process a single window
    python flow.py --start 2024-01-01T00:00:00 --end 2024-01-01T06:00:00

    # Re-run the same window (demonstrates caching -- tasks return instantly)
    python flow.py --start 2024-01-01T00:00:00 --end 2024-01-01T06:00:00

    # Serve as a deployment (for backfill.py to trigger)
    python flow.py --serve
"""

import argparse
import os
import random
import time
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from prefect import flow, task, get_run_logger
from prefect.cache_policies import INPUTS
from prefect.events import emit_event
from prefect.transactions import transaction
from prefect.variables import Variable


# ============================================================
# Data Models
# ============================================================


class ExtractResult(BaseModel):
    """Result from data extraction for a processing window."""

    record_count: int
    window_start: str
    window_end: str
    extract_timestamp: str
    source_system: str


class TransformResult(BaseModel):
    """Result from data transformation and validation."""

    input_records: int
    output_records: int
    rejected_records: int
    window_start: str
    window_end: str


class LoadResult(BaseModel):
    """Result from loading data to the target table."""

    records_loaded: int
    target_table: str
    window_start: str
    window_end: str
    load_timestamp: str


# ============================================================
# Tasks
# ============================================================


@task(
    name="extract-window-data",
    cache_policy=INPUTS,
    persist_result=True,
    retries=2,
    retry_delay_seconds=5,
)
def extract_window_data(
    window_start: str,
    window_end: str,
    source_system: str = "claims-warehouse",
) -> ExtractResult:
    """
    Extract data for the given processing window.

    On re-run with the same window boundaries, this returns instantly
    from cache. The INPUTS policy keys on window_start + window_end,
    so identical windows always produce cached results.
    """
    logger = get_run_logger()
    logger.info(f"Extracting data for window {window_start} to {window_end}")

    # Simulate extraction time
    time.sleep(random.uniform(2, 4))

    record_count = random.randint(8_000, 15_000)

    result = ExtractResult(
        record_count=record_count,
        window_start=window_start,
        window_end=window_end,
        extract_timestamp=datetime.now().isoformat(),
        source_system=source_system,
    )

    logger.info(f"Extracted {result.record_count:,} records from {source_system}")
    return result


@task(
    name="transform-records",
    cache_policy=INPUTS,
    persist_result=True,
)
def transform_records(extract_result: ExtractResult) -> TransformResult:
    """
    Transform extracted records -- validate, clean, enrich.

    Chained caching: if the extract result is cached and unchanged,
    this task also returns from cache. Pydantic models serialize
    deterministically, so cache keys are reliable.
    """
    logger = get_run_logger()
    logger.info(f"Transforming {extract_result.record_count:,} records")

    # Simulate transformation time
    time.sleep(random.uniform(2, 3))

    rejected = random.randint(10, int(extract_result.record_count * 0.02))
    output = extract_result.record_count - rejected

    result = TransformResult(
        input_records=extract_result.record_count,
        output_records=output,
        rejected_records=rejected,
        window_start=extract_result.window_start,
        window_end=extract_result.window_end,
    )

    logger.info(
        f"Transformed: {result.output_records:,} passed, "
        f"{result.rejected_records:,} rejected"
    )
    return result


@task(
    name="load-to-target",
    retries=3,
    retry_delay_seconds=10,
)
def load_to_target(transform_result: TransformResult) -> LoadResult:
    """
    Load transformed records to the target table.

    Wrapped in a transaction with a rollback hook. If anything
    downstream fails, the rollback cleans up partial writes.
    """
    logger = get_run_logger()
    logger.info(f"Loading {transform_result.output_records:,} records to target")

    # Simulate load time
    time.sleep(random.uniform(2, 4))

    result = LoadResult(
        records_loaded=transform_result.output_records,
        target_table="fact_claims_processed",
        window_start=transform_result.window_start,
        window_end=transform_result.window_end,
        load_timestamp=datetime.now().isoformat(),
    )

    logger.info(f"Loaded {result.records_loaded:,} records to {result.target_table}")
    return result


@load_to_target.on_rollback
def rollback_load(txn):
    """
    Rollback hook: clean up partial writes if the transaction fails.

    In production, this would DELETE records for the window from the
    target table. The cached extract and transform results remain
    valid, so a retry only re-executes the load.
    """
    logger = get_run_logger()
    logger.warning(
        "Rolling back load -- would DELETE partial records for this window"
    )


@task(
    name="update-completeness-boundary",
    retries=2,
    retry_delay_seconds=5,
)
def update_completeness_boundary(window_end: str) -> str:
    """
    Advance the completeness boundary to track data readiness.

    Uses Prefect Variables (key-value store) to maintain the latest
    completed window. Visible in the Prefect UI under Variables.
    Downstream systems check this to know when data is ready.
    """
    logger = get_run_logger()

    current_boundary = Variable.get("claims_completeness_boundary", default="none")
    logger.info(f"Current completeness boundary: {current_boundary}")

    # Only advance forward, never backward (handles out-of-order backfills)
    if current_boundary == "none" or window_end > current_boundary:
        Variable.set(
            name="claims_completeness_boundary",
            value=window_end,
            overwrite=True,
        )
        logger.info(f"Advanced completeness boundary: {current_boundary} -> {window_end}")
    else:
        logger.info(
            f"Boundary not advanced (processing older window): "
            f"{window_end} <= {current_boundary}"
        )

    return Variable.get("claims_completeness_boundary")


@task(
    name="emit-window-complete-event",
    retries=2,
    retry_delay_seconds=5,
)
def emit_window_complete(load_result: LoadResult, completeness_boundary: str):
    """
    Emit a custom event when a window completes processing.

    Visible in the Prefect Event Feed. Wire an Automation to this
    event to trigger downstream flows (aggregation, reporting, etc.)
    without polling.
    """
    logger = get_run_logger()

    emit_event(
        event="claims.window.completed",
        resource={
            "prefect.resource.id": (
                f"claims-pipeline.window.{load_result.window_start}"
            ),
            "prefect.resource.name": (
                f"Claims Window {load_result.window_start} "
                f"to {load_result.window_end}"
            ),
        },
        payload={
            "window_start": load_result.window_start,
            "window_end": load_result.window_end,
            "records_loaded": load_result.records_loaded,
            "target_table": load_result.target_table,
            "completeness_boundary": completeness_boundary,
            "load_timestamp": load_result.load_timestamp,
        },
    )

    logger.info(
        f"Emitted 'claims.window.completed' event for "
        f"{load_result.window_start}"
    )


# ============================================================
# Flow
# ============================================================


@flow(
    name="process-claims-window",
    flow_run_name="process-{window_start}-to-{window_end}",
    log_prints=True,
)
def process_claims_window(
    window_start: str = "2024-01-01T00:00:00",
    window_end: str = "2024-01-01T06:00:00",
) -> dict:
    """
    Process claims data for a specific time window.

    The flow operates on the assigned window boundaries, not the system
    clock. Running the same window twice produces cached results for
    extract and transform tasks, demonstrating idempotent reprocessing.

    Args:
        window_start: ISO format start of the processing window.
        window_end: ISO format end of the processing window.
    """
    print(f"\n{'=' * 60}")
    print(f"CLAIMS WINDOW PROCESSOR")
    print(f"Window: {window_start} to {window_end}")
    print(f"{'=' * 60}\n")

    # Extract -> Transform -> Load within a transaction
    # If the load fails, the rollback hook fires and cached
    # extract/transform results remain valid for retry
    with transaction():
        extract_result = extract_window_data(
            window_start=window_start,
            window_end=window_end,
        )

        transform_result = transform_records(extract_result)

        load_result = load_to_target(transform_result)

    # Update completeness boundary after successful transaction
    completeness_boundary = update_completeness_boundary(window_end)

    # Emit event for downstream automation
    emit_window_complete(load_result, completeness_boundary)

    print(f"\n{'=' * 60}")
    print(f"WINDOW COMPLETE")
    print(f"  Records: {load_result.records_loaded:,}")
    print(f"  Target: {load_result.target_table}")
    print(f"  Completeness boundary: {completeness_boundary}")
    print(f"{'=' * 60}\n")

    return {
        "window_start": window_start,
        "window_end": window_end,
        "records_loaded": load_result.records_loaded,
        "completeness_boundary": completeness_boundary,
    }


# ============================================================
# Entry Point
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="Process claims data for a specific time window",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process a single window
    python flow.py --start 2024-01-01T00:00:00 --end 2024-01-01T06:00:00

    # Re-run same window (demonstrates caching)
    python flow.py --start 2024-01-01T00:00:00 --end 2024-01-01T06:00:00

    # Serve as a deployment (for backfill.py to trigger)
    python flow.py --serve
        """,
    )
    parser.add_argument("--start", default=None, help="Window start (ISO format)")
    parser.add_argument("--end", default=None, help="Window end (ISO format)")
    parser.add_argument(
        "--serve", action="store_true", help="Serve as a deployment"
    )
    args = parser.parse_args()

    if args.serve:
        process_claims_window.serve(
            name="claims-window-processor",
            tags=["temporal-demo", "claims"],
            parameters={
                "window_start": "2024-01-01T00:00:00",
                "window_end": "2024-01-01T06:00:00",
            },
        )
    else:
        if args.start and args.end:
            start, end = args.start, args.end
        else:
            now = datetime.now().replace(minute=0, second=0, microsecond=0)
            start = (now - timedelta(hours=6)).isoformat()
            end = now.isoformat()

        process_claims_window(window_start=start, window_end=end)


if __name__ == "__main__":
    main()
