import asyncio
from os import listdir
from pathlib import Path

from src.server_info import DATA_DIR, SERVER_INFO
import requests

RESTART_OPTIONS = [
    {
        "name": "pc-ept",
        "value": False
    },
    {
        "name": "cog",
        "value": False
    },
    {
        "name": "gltf",
        "value": False
    }
]


def run_coroutine_in_thread(coroutine, *args):
    asyncio.run(coroutine(*args))


async def request_odm_stitch(uuid, id):
    print(f'request_odm_stitch: {uuid} {id}')
    # Path(DATA_DIR) / id / 에 flag생성
    with open(Path(DATA_DIR) / id / "step2_uploading", "w") as f:
        f.write("Stitching in progress")

    uploading_file = Path(DATA_DIR) / id / "step2_uploading"

    for file_name in listdir(Path(DATA_DIR) / id / "images"):
        file_path = Path(DATA_DIR) / id / "images" / file_name
        print(f"uploading {file_path}")
        response = requests.post(f"{SERVER_INFO['ODM_URL']}/task/new/upload/{uuid}",
                                 files={"images": open(file_path, "rb")})
        print(f"upload_response: {response.json()}")
        if 'error' in response.json() and response.json()['error'].startswith("Invalid uuid"):
            response = requests.post(f"{SERVER_INFO['ODM_URL']}/task/restart", json={"uuid": uuid, "options": RESTART_OPTIONS})
            if uploading_file.exists():
                uploading_file.unlink()
            return response.json()
        if response.status_code != 200:
            print(f"upload failed: {file_path}")
            if uploading_file.exists():
                uploading_file.unlink()
            return
    # Path(DATA_DIR) / id / 에 flag삭제
    uploading_file = Path(DATA_DIR) / id / "step2_uploading"
    if uploading_file.exists():
        uploading_file.unlink()
    print(f"{SERVER_INFO['ODM_URL']}/task/new/commit/{uuid}")
    response = requests.post(f"{SERVER_INFO['ODM_URL']}/task/new/commit/{uuid}")
    print(f"commit_response: {response}")
    print(f"{response.json()}")

    return response.json()
