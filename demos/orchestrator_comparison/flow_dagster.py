"""
Dagster equivalent of the Prefect Quick Start flow.

This replicates the same logic: fetch a GitHub repo's info,
print stargazers, and print the number of contributors.

Dagster uses a Software-Defined Assets (SDA) paradigm. Everything
is modeled as an "asset" - a persistent artifact that your pipeline
produces. This is powerful for data lineage but adds conceptual
overhead when your workflow is just "run these steps in order."

Compare with flow.py to see the difference.
"""

import httpx
from dagster import (
    AssetExecutionContext,
    Definitions,
    RetryPolicy,
    asset,
    define_asset_job,
    Config,
)


# ── Configuration ────────────────────────────────────────────────────
# Dagster uses Pydantic-based Config objects for parameterization.
# You can't just pass arguments to a function like in Prefect.
# Each asset that needs config gets its own Config class.

class RepoConfig(Config):
    repo_owner: str = "PrefectHQ"
    repo_name: str = "prefect"


# ── Asset 1: repo_info ──────────────────────────────────────────────
# In Dagster, this isn't a "task" - it's an "asset," a materialized
# artifact. The framework expects you to think in terms of data
# products, not steps. Even if you just want to call an API and
# pass the result along, you're "materializing an asset."

@asset(
    description="Raw GitHub repository metadata.",
    group_name="github",
)
def repo_info(context: AssetExecutionContext, config: RepoConfig) -> dict:
    """Get info about a repo."""
    url = f"https://api.github.com/repos/{config.repo_owner}/{config.repo_name}"
    api_response = httpx.get(url)
    api_response.raise_for_status()
    info = api_response.json()

    # Dagster encourages structured metadata on every asset
    # materialization. Useful for the UI, but mandatory ceremony
    # for what would be a print() in Prefect.
    context.log.info("Stars 🌠 : %s", info["stargazers_count"])

    return info


# ── Branching: the gap ────────────────────────────────────────────────
# In Prefect, the flow decides at runtime whether to continue:
#
#   info = get_repo_info(repo_owner, repo_name)
#   if info:
#       contributors = get_contributors(info)
#   else:
#       print("This isn't a repo")
#
# That's just Python. The if/else runs at execution time, inspecting
# real return values from real function calls.
#
# In Dagster, you can't do this. Asset dependencies are static --
# they're resolved at import time, not at runtime. The contributors
# asset ALWAYS runs after repo_info materializes. There's no way to
# say "if repo_info returned nothing, skip contributors."
#
# Your options:
#   1. Guard inside the downstream asset (check for None, return empty).
#      But the asset still "materializes" -- it's not a true skip.
#   2. Use @graph_asset with @op-level branching. Adds another layer
#      of abstraction and defeats the purpose of the asset model.
#   3. Use multi_asset with AssetSpec(skippable=True) to conditionally
#      yield MaterializeResult for some outputs but not others. This is
#      the closest Dagster gets, but it requires restructuring into a
#      multi_asset -- not just writing an if/else.
#   4. Use sensors or AutomationConditions. Way too heavy for an
#      if/else statement.
#
# Same story for try/except. In Prefect, the flow wraps tasks in a
# try/except and handles errors inline. In Dagster, if an asset
# raises, the execution engine handles it -- there's no orchestration
# function where you catch and recover across multiple assets.

# ── Asset 2: contributors ───────────────────────────────────────────
# This asset depends on repo_info. By default, Dagster infers the
# dependency from the function signature -- the parameter name must
# match the upstream asset name. Rename one and not the other, and
# the dependency silently breaks. You can use AssetIn to explicitly
# decouple parameter names from asset keys, but the default behavior
# makes renames a silent failure if you're not careful.
#
# Retries: Dagster uses a RetryPolicy object. No inline shorthand
# like retries=2 - you instantiate a policy class.

@asset(
    description="List of contributors for the GitHub repository.",
    group_name="github",
    retry_policy=RetryPolicy(max_retries=2, delay=5),
)
def contributors(context: AssetExecutionContext, repo_info: dict) -> list:
    """Get contributors for a repo."""
    contributors_url = repo_info["contributors_url"]
    response = httpx.get(contributors_url)
    response.raise_for_status()
    contribs = response.json()

    context.log.info("Number of contributors 👷: %s", len(contribs))

    return contribs


# ── Job definition ───────────────────────────────────────────────────
# Assets don't run on their own. You need a "job" to materialize them.
# The job selects which assets to include and can be triggered manually
# or on a schedule.

repo_info_job = define_asset_job(
    name="repo_info_job",
    selection=["repo_info", "contributors"],
    description="Fetch GitHub repo info and contributors.",
)


# ── Definitions (the "repository") ──────────────────────────────────
# All assets, jobs, schedules, sensors, and resources must be
# registered in a single Definitions object. This is the entrypoint
# Dagster uses to discover your code. Miss something here and it
# doesn't exist as far as Dagster is concerned.

defs = Definitions(
    assets=[repo_info, contributors],
    jobs=[repo_info_job],
)


# ── No __main__, no flow-level retries ────────────────────────────────
# You can't just run this file. You need the Dagster CLI:
#
#   dagster dev -f flow_dagster.py
#
# This launches a web server (Dagit) where you manually trigger
# the job through the UI, or use:
#
#   dagster job execute -f flow_dagster.py -j repo_info_job
#
# There's no equivalent to:
#   if __name__ == "__main__":
#       repo_info()
#
# Also missing: flow-level retries. Prefect's @flow(retries=1) reruns
# the entire flow on failure. Dagster's define_asset_job accepts
# op_retry_policy, but that retries individual assets, not the whole
# run. For run-level retries, you configure dagster.yaml or set a
# dagster/max_retries tag on the job -- infrastructure and config
# concerns, not a one-liner in your code.
