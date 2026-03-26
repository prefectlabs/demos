"""
Airflow equivalent of the Prefect Quick Start flow (Classic Operators).

This DAG replicates the same logic: fetch a GitHub repo's info,
print stargazers, and print the number of contributors.

Uses the classic Operator pattern (pre-TaskFlow API) which is how
most production Airflow codebases are written. Functions are wired
together with PythonOperator and data passes through XCom manually.

Compare with:
  - flow.py                       → Prefect (the baseline)
  - flow_airflow_taskflow.py      → Airflow TaskFlow API (@task/@dag)
  - flow_dagster.py               → Dagster assets
"""

import json
import logging
from datetime import datetime, timedelta

import httpx
from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)


# ── Callable functions (defined OUTSIDE the DAG) ─────────────────────
# In classic Airflow, your business logic lives in standalone functions.
# They receive an implicit **kwargs (or explicit ti) to access XCom,
# params, and other Airflow context. Your code is always aware it's
# running inside Airflow.


def _get_repo_info(**kwargs):
    """Get info about a repo and push it to XCom."""
    params = kwargs["params"]
    repo_owner = params["repo_owner"]
    repo_name = params["repo_name"]

    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    api_response = httpx.get(url)
    api_response.raise_for_status()
    repo_info = api_response.json()

    # Must explicitly push to XCom so downstream tasks can pull it.
    # XCom stores data in the Airflow metadata DB (Postgres/MySQL),
    # so large payloads need a custom XCom backend (S3, GCS, etc.).
    kwargs["ti"].xcom_push(key="repo_info", value=json.dumps(repo_info))


def _print_stars(**kwargs):
    """Pull repo info from XCom and print the stargazer count."""
    ti = kwargs["ti"]
    repo_info_json = ti.xcom_pull(task_ids="get_repo_info", key="repo_info")
    repo_info = json.loads(repo_info_json)
    logger.info("Stars 🌠 : %s", repo_info["stargazers_count"])


def _get_contributors(**kwargs):
    """Pull repo info from XCom, fetch contributors, push back to XCom."""
    ti = kwargs["ti"]
    repo_info_json = ti.xcom_pull(task_ids="get_repo_info", key="repo_info")
    repo_info = json.loads(repo_info_json)

    contributors_url = repo_info["contributors_url"]
    response = httpx.get(contributors_url)
    response.raise_for_status()
    contributors = response.json()

    ti.xcom_push(key="contributors", value=json.dumps(contributors))


def _print_contributors(**kwargs):
    """Pull contributors from XCom and print the count."""
    ti = kwargs["ti"]
    contributors_json = ti.xcom_pull(
        task_ids="get_contributors", key="contributors"
    )
    contributors = json.loads(contributors_json)
    logger.info("Number of contributors 👷: %s", len(contributors))


# ── DAG definition ───────────────────────────────────────────────────

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="repo_info",
    default_args=default_args,
    description="Given a GitHub repository, logs stargazers and contributors.",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["github", "quick-start"],
    params={
        "repo_owner": "PrefectHQ",
        "repo_name": "prefect",
    },
) as dag:

    # ── Task instantiation ───────────────────────────────────────────
    # Each task is an Operator instance. The function is passed as
    # python_callable, not called directly. You don't call your code;
    # the scheduler does, in a separate process, possibly on a
    # different machine.

    get_repo_info = PythonOperator(
        task_id="get_repo_info",
        python_callable=_get_repo_info,
    )

    print_stars = PythonOperator(
        task_id="print_stars",
        python_callable=_print_stars,
    )

    # Retries configured per-operator, overriding default_args.
    get_contributors = PythonOperator(
        task_id="get_contributors",
        python_callable=_get_contributors,
        retries=2,
        retry_delay=timedelta(seconds=5),
    )

    print_contributors = PythonOperator(
        task_id="print_contributors",
        python_callable=_print_contributors,
    )

    # ── Dependency wiring ────────────────────────────────────────────
    # Bitshift operators define execution order. Data flow is implicit;
    # you have to know which task_id and XCom key to pull from.
    # Get any of these strings wrong and it silently returns None.
    #
    # ── Branching: the gap ────────────────────────────────────────────
    # In Prefect, the flow inspects task results at runtime:
    #
    #   info = get_repo_info(repo_owner, repo_name)
    #   if info:
    #       contributors = get_contributors(info)
    #   else:
    #       print("This isn't a repo")
    #
    # In classic Airflow, the DAG structure is static. To branch, you
    # need a BranchPythonOperator -- a dedicated operator that returns
    # the task_id of the next task to run. The branch logic lives in
    # a separate function, not inline with your orchestration code.
    # It works, but it's another operator to wire, another XCom to
    # manage, and another place for string-based task_ids to break.
    #
    # Flow-level try/except is also not possible here. If a task
    # raises, Airflow marks it FAILED and you handle it via
    # on_failure_callback or trigger_rule on downstream tasks --
    # not with Python error handling.

    get_repo_info >> [print_stars, get_contributors]
    get_contributors >> print_contributors
