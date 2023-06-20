import json
import os
import pytest
import shutil
import requests


@pytest.fixture(scope="module")
def config():
    with open("config.json", "r") as f:
        config = json.load(f)
    return config


@pytest.fixture
def workspace(config):
    yield config["workspace_path"]
    # teardown after test function completes
    for filename in os.listdir(config["workspace_path"]):
        file_path = os.path.join(config["workspace_path"], filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")


@pytest.fixture(autouse=True)
def server_response(request, config):
    task = request.param  # The task is passed in indirectly
    print(f"Server starting at {request.module}")
    response = requests.post(
        f"{config['url']}:{config['hostname']}", data={"task": task}
    )
    assert (
        response.status_code == 200
    ), f"Request failed with status code {response.status_code}"
