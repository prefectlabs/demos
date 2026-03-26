"""
Airflow TaskFlow API equivalent of the Prefect Quick Start flow.

This DAG replicates the same logic: fetch a GitHub repo's info,
print stargazers, and print the number of contributors.

Uses the TaskFlow API (@task / @dag decorators) introduced in
Airflow 2.0. This is Airflow's answer to the verbosity of the
classic Operator pattern -- closer to how Prefect works, but
still carrying Airflow's scheduling and infrastructure baggage.

Compare with:
  - flow.py              → Prefect (the baseline)
  - flow_airflow.py      → Airflow classic Operators
  - flow_dagster.py      → Dagster assets
"""

import logging
from datetime import datetime, timedelta

import httpx
from airflow.decorators import dag, task

logger = logging.getLogger(__name__)


# ── Tasks ─────────────────────────────────────────────────────────────
# With TaskFlow, you decorate plain functions with @task. Return values
# are automatically serialized to XCom -- no more manual xcom_push/pull.
#
# This feels closer to Prefect's @task, but there are key differences:
#
# 1. You can't run these functions outside of Airflow. They're still
#    bound to the scheduler, the metadata DB, and the executor.
#
# 2. Return values get serialized to the Airflow metadata DB by default.
#    Large payloads still need a custom XCom backend. Prefect tasks just
#    return Python objects in-process -- no serialization overhead.
#
# 3. The @task decorator doesn't support all Operator features. Need
#    a BashOperator, KubernetesPodOperator, or any non-Python operator?
#    You're back to the classic pattern and wiring XCom manually.


@task
def get_repo_info(repo_owner: str, repo_name: str) -> dict:
    """Get info about a repo."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    api_response = httpx.get(url)
    api_response.raise_for_status()
    return api_response.json()


@task
def print_stars(repo_info: dict):
    """Print the stargazer count."""
    logger.info("Stars 🌠 : %s", repo_info["stargazers_count"])


@task(retries=2, retry_delay=timedelta(seconds=5))
def get_contributors(repo_info: dict) -> list:
    """Get contributors for a repo."""
    contributors_url = repo_info["contributors_url"]
    response = httpx.get(contributors_url)
    response.raise_for_status()
    return response.json()


@task
def print_contributors(contributors: list):
    """Print the contributor count."""
    logger.info("Number of contributors 👷: %s", len(contributors))


# ── DAG definition ────────────────────────────────────────────────────
# The @dag decorator replaces the `with DAG(...) as dag:` context
# manager. The decorated function becomes the DAG's entrypoint.
#
# This is cleaner than the classic pattern, but notice you still need:
#   - default_args dict
#   - start_date (even for unscheduled DAGs)
#   - catchup=False (to avoid backfill surprises)
#   - explicit schedule=None
#
# In Prefect, you'd just write:
#   @flow
#   def repo_info(repo_owner="PrefectHQ", repo_name="prefect"):
#
# That's it. No scheduling config, no start_date, no default_args.
# You run it when you want. Scheduling is a deployment concern,
# not a code concern.

@dag(
    dag_id="repo_info_taskflow",
    default_args={
        "owner": "data-team",
        "depends_on_past": False,
        "retries": 0,
        "retry_delay": timedelta(minutes=5),
    },
    description="Given a GitHub repository, logs stargazers and contributors.",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["github", "quick-start", "taskflow"],
)
def repo_info():
    # ── Orchestration logic ───────────────────────────────────────
    # This looks deceptively like Prefect. You call tasks like
    # functions, pass return values as arguments, and Airflow
    # infers the dependency graph. Nice, right?
    #
    # But there's a catch: these aren't real function calls.
    # They return XComArg proxy objects, not actual data.
    # You can't inspect or branch on return values here.
    #
    # This would NOT work:
    #   info = get_repo_info("PrefectHQ", "prefect")
    #   if info["stargazers_count"] > 1000:   # TypeError
    #       ...
    #
    # In Prefect, that just works -- tasks return real Python
    # objects and you branch however you want.

    info = get_repo_info("PrefectHQ", "prefect")
    print_stars(info)

    contribs = get_contributors(info)
    print_contributors(contribs)


# Instantiate the DAG. Without this line, Airflow won't discover it.
# The @dag decorator returns a factory, not a DAG instance.
repo_info()


# ── Still no __main__ ─────────────────────────────────────────────────
# Even with TaskFlow, you can't just run this file:
#
#   python flow_airflow_taskflow.py   # Does nothing useful
#
# You need the full Airflow stack:
#   airflow dags test repo_info_taskflow 2024-01-01
#
# Or start the webserver + scheduler and trigger from the UI.
#
# Compare with Prefect:
#   python flow.py                    # Just works
