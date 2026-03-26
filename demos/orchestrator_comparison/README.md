# Orchestrator Comparison

Same workflow. Four implementations. One question: how much of your code is actually yours, and how much belongs to the framework?

Each file fetches a GitHub repo's metadata and contributor list. Simple enough to read in one sitting. Complex enough to expose where these tools start fighting you.

## The Point

Airflow and Dagster require you to learn the framework before you can write anything. You think in DAGs, assets, operators, and XCom before you think about your problem. Prefect flips that. You write Python. It works. Then you grow into the platform features (retries, scheduling, observability, transactions, assets) when you need them. Not before.

## Files in this demo

| File | Framework | What You'll See |
|---|---|---|
| `flow.py` | **Prefect** | The baseline. Python functions with decorators. That's it. |
| `flow_dagster.py` | Dagster | Software-Defined Assets. Same logic, more ceremony, more concepts to learn first. |
| `flow_airflow.py` | Airflow (Classic) | `PythonOperator` + manual XCom wiring. Your code knows it's inside Airflow. |
| `flow_airflow_taskflow.py` | Airflow (TaskFlow) | `@task`/`@dag` decorators. Looks closer to Prefect. Still can't run it without the full stack. |

## Run the Prefect Version

```bash
uv pip install prefect httpx
uv run flow.py
```

That's it. The comments in each competitor file explain what you'd need to get theirs running.
