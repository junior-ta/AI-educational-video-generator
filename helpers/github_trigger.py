"""I use this to start working when a job is available"""

import os
import requests


def trigger_worker_run(ref: str = "main") -> bool:
    #Fires worker.yml immediately via workflow_dispatch

    url = (
        f"https://api.github.com/repos/{os.environ['GITHUB_REPO']}"
        f"/actions/workflows/{os.environ['GITHUB_WORKFLOW_FILE']}/dispatches"
    )
    headers = {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.post(url, headers=headers, json={"ref": ref})
    return resp.status_code == 204  # 204 No Content = accepted