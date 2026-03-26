# Temporal Orchestration Demo

A working demo of temporal orchestration patterns in Prefect. Shows how Prefect's primitives -- flow parameters, task caching, transactions, variables, and custom events -- compose into the patterns teams commonly need for window-based data processing.

The flow simulates a claims data window processor. Each run receives explicit window boundaries as parameters and processes data for that slice. Task-level caching makes reprocessing idempotent without custom deduplication logic, a completeness boundary tracked via Prefect Variables gives downstream systems a queryable "data is ready through X" signal, and custom events open the door to automation-driven downstream triggering without polling.

The ETL steps are wrapped in a [transaction](https://docs.prefect.io/v3/develop/transactions) with rollback hooks, which is Prefect's take on durable execution for data workflows. Rather than replaying an entire event history to recover state, Prefect persists task results and resumes from the last successful checkpoint. If the load fails, the rollback hook cleans up partial writes, cached extract and transform results stay valid, and the retry only re-executes what actually failed. The Prefect team wrote about this philosophy in detail [here](https://www.prefect.io/blog/decomposed-durability-a-different-approach-to-durable-execution).

## Requirement Mapping

| Requirement | Prefect Feature | Where in Code |
|---|---|---|
| Execution based on defined data windows | Flow parameters (`window_start`, `window_end`) | `flow.py` -- flow signature |
| Clear start/end boundaries per window | `flow_run_name` template | `@flow(flow_run_name="process-{window_start}-to-{window_end}")` |
| Consistent, repeatable results | `cache_policy=INPUTS` + `persist_result=True` | `extract_window_data`, `transform_records` |
| Controlled reprocessing of historical windows | `run_deployment()` in a loop | `backfill.py` |
| Configurable completeness boundary | `Variable.set()` / `Variable.get()` | `update_completeness_boundary` task |
| Downstream processing gating | `emit_event()` + Automations | `emit_window_complete` task |
| Atomic writes with rollback | `transaction()` + `@task.on_rollback` | ETL block in main flow |
| Reprocessing order and concurrency | Work pool + queue config | UI/CLI (see below) |

## Setup

```bash
cd demos/temporal-orchestration
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires a Prefect Cloud account or local Prefect server for Variables and Events.

## Deployment

Deploy to Prefect Cloud using managed execution (no infrastructure setup needed):

```bash
python deploy.py
```

This pulls code from GitHub at runtime and installs dependencies automatically. Requires:
- Logged into Prefect Cloud (`prefect cloud login`)
- A `GitHubRepository` block named `prefect-work-repo`
- A managed execution work pool (default: `managed`)

After deploying, trigger runs via CLI, Python, or the UI:

```bash
# Via CLI
prefect deployment run 'process-claims-window/claims-window-processor' \
    -p window_start=2024-01-01T00:00:00 \
    -p window_end=2024-01-01T06:00:00

# Via backfill script
python backfill.py --days 3
```

## Running the Demo

### 1. Process a single window

```bash
python flow.py --start 2024-01-01T00:00:00 --end 2024-01-01T06:00:00
```

### 2. Re-run the same window (caching demo)

```bash
python flow.py --start 2024-01-01T00:00:00 --end 2024-01-01T06:00:00
```

Extract and transform tasks return instantly from cache. Load re-executes (writes are not cached by design).

### 3. Backfill historical windows

Two options depending on whether you're running locally or deployed to Cloud.

**Local (serve mode):**

```bash
# Terminal 1: serve the flow as a local deployment. This just means you're spinning up a worker
# on your machine so that prefect cloud can use your machine's compute to execute the flow.
python flow.py --serve

# Terminal 2: trigger backfill
python backfill.py --days 3 --dry-run    # preview first
python backfill.py --days 3              # trigger 12 runs (3 days x 4 windows/day)
```

**Cloud (after deploy.py):**

No serve step needed -- the deployment already exists in Cloud.

```bash
# Single window via CLI
prefect deployment run 'process-claims-window/claims-window-processor' \
    -p window_start=2024-01-01T00:00:00 \
    -p window_end=2024-01-01T06:00:00

# Single window via UI
# Deployments -> claims-window-processor -> Run -> Custom Run -> set parameters

# Backfill via script
python backfill.py --days 3 --dry-run    # preview first
python backfill.py --days 3              # trigger 12 runs on managed infrastructure
```

Each window gets its own flow run. Work pool concurrency controls how many run in parallel.

## What to Observe in the Prefect UI

**Flow Runs page** -- Each run is named `process-{start}-to-{end}`. Every window is visually distinct and searchable.

**Task states on re-run** -- Click into a re-run. `extract-window-data` and `transform-records` show "Cached" state. They completed instantly without re-executing. That's idempotency with zero custom deduplication code.

**Variables page** -- `claims_completeness_boundary` advances as windows complete. This is a live, visible completeness tracker that downstream systems can query.

**Events page** -- `claims.window.completed` events appear with full payload: window boundaries, record counts, completeness boundary. This is the trigger point for downstream automations.

## Platform Configuration (UI/CLI)

These features are configured in the Prefect platform, not in flow code. They control how runs execute alongside each other.

### Work pool concurrency (system-wide circuit breaker)

```bash
# Limit total concurrent runs across the pool
prefect work-pool update <pool-name> --concurrency-limit 3
```

### Work queue priorities (separate critical from backfill)

```bash
# Critical processing runs first (lower number = higher priority)
prefect work-queue create critical --pool <pool-name> --priority 1
prefect work-queue create backfill --pool <pool-name> --priority 10
```

### Global concurrency limits (fine-grained semaphores)

```bash
# Limit concurrent database connections across all flows
prefect gcl create database-connections --limit 5
```

Use in code with `from prefect.concurrency.sync import concurrency`.

### Automations (event-driven downstream triggers)

Configure in the UI: **Automations > Create**

- **Trigger**: Custom event `claims.window.completed`
- **Action**: Run deployment (e.g., `downstream-aggregation/daily-rollup`)
- **Parameters**: Template from event payload (`{{ event.payload.window_start }}`)

No polling. The upstream flow emits the event, the automation triggers downstream.

## Live Walkthrough Script

For presenting to the evaluation team:

1. **Run a single window** (2 min) -- show flow run name, task graph, Variable update, Event in the UI
2. **Re-run the same window** (1 min) -- "Same command. Watch the task states." Extract and transform show Cached.
3. **Serve + backfill** (2 min) -- 12 runs queue up, named by window, concurrency-controlled by the pool
4. **Walk through the transaction code** (1 min) -- show `with transaction()` and the `on_rollback` hook
5. **Show the automation wiring** (1 min) -- where `claims.window.completed` triggers downstream
6. **Show the Variable** (30 sec) -- "This is how downstream consumers know data is complete through this timestamp"

## Architecture

```
                    ┌──────────────────────────┐
                    │  backfill.py              │
                    │  run_deployment() loop    │
                    └──────────┬───────────────┘
                               │ triggers N runs
                               ▼
┌─────────────────────────────────────────────────────────┐
│  process_claims_window(window_start, window_end)        │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  transaction()                                  │    │
│  │                                                 │    │
│  │  extract_window_data  ──► transform_records     │    │
│  │  (INPUTS cache)          (INPUTS cache)         │    │
│  │                              │                  │    │
│  │                              ▼                  │    │
│  │                       load_to_target            │    │
│  │                       (on_rollback hook)        │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  update_completeness_boundary  ──► Variable.set()       │
│                                                         │
│  emit_window_complete  ──► Event Feed ──► Automations   │
└─────────────────────────────────────────────────────────┘
```
