import httpx
from prefect import flow, task

@task
def get_repo_info(repo_owner: str, repo_name: str):
    """Get info about a repo."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    api_response = httpx.get(url)
    api_response.raise_for_status()
    repo_info = api_response.json()
    return repo_info


@task(retries=2, retry_delay_seconds=5, log_prints=True)
def get_contributors(repo_info: dict):
    """Get contributors for a repo"""
    contributors_url = repo_info["contributors_url"]
    response = httpx.get(contributors_url)
    response.raise_for_status()
    contributors = response.json()
    return contributors


@flow(retries=1)
def repo_info(repo_owner: str = "PrefectHQ", repo_name: str = "prefect"):
    """
    Given a GitHub repository, logs the number of stargazers
    and contributors for that repo.
    """
    try:
        info = get_repo_info(repo_owner, repo_name)
        if info:
            print(f"Stars 🌠 : {info['stargazers_count']}")
            contributors = get_contributors(info)
            print(f"Number of contributors 👷: {len(contributors)}")
        else:
            print("This isn't a repo")
    except Exception as exc:
        print(exc)


if __name__ == "__main__":
    repo_info()
