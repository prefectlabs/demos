"""
Deploy the Temporal Orchestration Demo to Prefect Cloud
=======================================================

Uses Prefect's managed execution work pool -- no infrastructure setup needed.
Code is pulled from GitHub at runtime.

PREREQUISITES:

1. Be logged into Prefect Cloud:
   prefect cloud login

2. Have a GitHubRepository block configured:
   prefect block ls github-repository

3. Have a managed execution work pool (default: "managed")

USAGE:
    python deploy.py

After deployment, run the flow:

    Via CLI:
        prefect deployment run 'process-claims-window/claims-window-processor' \
            -p window_start=2024-01-01T00:00:00 \
            -p window_end=2024-01-01T06:00:00

    Via Python (backfill):
        python backfill.py --days 3

    Via Prefect Cloud UI:
        Deployments -> claims-window-processor -> Run
"""

from prefect import flow
from prefect_github.repository import GitHubRepository


RUNTIME_PACKAGES = [
    "prefect>=3.4.0",
    "pydantic>=2.0.0",
]


def main():
    """Deploy the temporal orchestration demo flow."""

    source = GitHubRepository.load("prefect-work-repo")

    flow.from_source(
        source=source,
        entrypoint="demos/temporal-orchestration/flow.py:process_claims_window",
    ).deploy(
        name="claims-window-processor",
        work_pool_name="managed",
        job_variables={
            "env": {
                "EXTRA_PIP_PACKAGES": " ".join(RUNTIME_PACKAGES),
            }
        },
        parameters={
            "window_start": "2024-01-01T00:00:00",
            "window_end": "2024-01-01T06:00:00",
        },
        tags=["temporal-demo", "claims"],
        description="""
            Claims Window Processor -- Temporal Orchestration Demo

            Processes claims data for a specific time window. Demonstrates
            flow parameters, task caching, result persistence, transactions,
            variables, custom events, and backfill orchestration.

            Run with custom windows:
                -p window_start=2024-03-01T00:00:00
                -p window_end=2024-03-01T06:00:00

            For backfill, use backfill.py to trigger multiple windows.
        """.strip(),
    )


if __name__ == "__main__":
    main()
