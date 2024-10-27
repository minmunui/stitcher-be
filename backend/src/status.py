import os
from datetime import datetime
import requests

from src.server_info import SERVER_INFO

from src.file_query import DATA_PATH, get_full_name_by_data_name, get_uuid_by_name

from backend.src.utils import convert_time

DATA_STATUS = {
    "UPLOADING": 0,
    "READY": 1,
    "ONPROGRESS": 2,
    "DONE": 3,
    "ERROR": 4
}

ODM_STATUS = {
    "QUEUED": 10,
    "RUNNING": 20,
    "FAILED": 30,
    "COMPLETED": 40,
    "CANCELED": 50
}



"""
    데이터의 상태를 확인하는 함수들을 정의합니다.
    데이터의 상태는 다음과 같이 정의합니다.
    UPLOADING: 데이터가 업로드 중인 상태
    READY: 데이터가 업로드가 완료되어 정합 가능한 상태
    ONPROGRESS: 데이터가 정합 중인 상태
    DONE: 데이터 정합이 완료된 상태
    ERROR: 데이터 정합 중 에러가 발생한 상태
    
    모든 데이터의 폴더는 다음과 같은 형식으로 구성됩니다.
    {데이터 이름};{UUID}
    예를 들어, 데이터 이름이 test이고 UUID가 1234인 경우
    test;1234
"""


def get_time_from_timestamp(timestamp: int) -> datetime:
    timestamp = timestamp / 1000
    return datetime.fromtimestamp(timestamp)




def get_data_status_step1(dir_name: str) -> tuple[str, int, dict]:
    """

    :param dir_name:
    :return:
    """
    datalist = os.listdir(DATA_PATH)

    # 업로드 중인 데이터
    for data in datalist:
        if data == dir_name:
            uploaded_time = os.path.getctime(os.path.join(DATA_PATH, data))
            uploaded_time = datetime.fromtimestamp(uploaded_time)
            return uploaded_time, 0, {
                "status": DATA_STATUS["UPLOADING"],
                "data": {"startedAt": uploaded_time}
            }

    full_name = get_full_name_by_data_name(dir_name)
    # 존재하지 않는 파일
    if full_name is None:
        print(f"Error: {dir_name} is not found")
        return "", 0, {
            "status": DATA_STATUS["ERROR"],
            "data": {"errorLog": "Data not found"}
        }

    data_path = os.path.join(DATA_PATH, get_full_name_by_data_name(full_name))
    opencv_path = os.path.join(data_path, "opencv-output")
    image_path = os.path.join(data_path, "images")
    n_images = len(os.listdir(image_path))
    uploaded_time = os.path.getctime(data_path)
    uploaded_time = convert_time(datetime.fromtimestamp(uploaded_time))
    # 정합 전인 데이터
    # data_path에 opencv-output이 존재하지 않으면 정합 전
    if not os.path.exists(opencv_path):
        return uploaded_time, n_images, {
            "status": DATA_STATUS["READY"],
            "data": {"uploadedAt": uploaded_time}
        }

    # 정합 에러 데이터
    # data_path에 opencv-output이 존재하고, 그 폴더에 error.txt가 존재하면 정합 에러
    if os.path.exists(os.path.join(data_path, "opencv-output", "error.txt")):
        # 에러 로그를 읽어서 반환
        with open(os.path.join(data_path, "opencv-output", "error.txt"), "r") as f:
            error_log = f.read()
        return uploaded_time, n_images, {
            "status": DATA_STATUS["ERROR"],
            "data": {"errorLog": error_log}
        }

    # 정합 중 혹은 완료 데이터
    n_cluster = 0
    current_cluster = 0
    uploaded_time = None
    # data_path에 opencv-output이 존재하지만, opencv-output에 c로 시작하는 폴더가 존재하면 정합 중
    for cluster in os.listdir(opencv_path):
        if cluster.startswith("c"):
            n_cluster = cluster.split('_')[1].split('.')[0]
            uploaded_time = os.path.getctime(os.path.join(opencv_path, cluster))
            uploaded_time = datetime.fromtimestamp(uploaded_time)
        if cluster.startswith("opencv_"):
            if current_cluster < int(cluster.split('_')[1].split('.')[0]):
                current_cluster = int(cluster.split('_')[1].split('.')[0])

    # 정합이 완료된 경우
    if current_cluster == n_cluster:
        return uploaded_time, n_images, {
            "status": DATA_STATUS["DONE"],
            "data": {"dataPath": data_path}
        }
    # 정합 중
    else:
        return uploaded_time, n_images, {
            "status": DATA_STATUS["ONPROGRESS"],
            "data": {"startedAt": uploaded_time, "nCluster": n_cluster, "currentCluster": current_cluster}
        }


def get_data_status_step2(dir_name: str) -> dict:
    """

    :param dir_name:
    :return:
    """
    # localhost:3000/task/{dir_name}/info 로 요청 보내기
    uuid = get_uuid_by_name(dir_name)
    uploaded_time = os.path.getctime(os.path.join(DATA_PATH, get_full_name_by_data_name(dir_name)))
    if uuid is None:
        return {
            "status": DATA_STATUS["READY"],
            "data": {"uploadedAt": uploaded_time}
        }
    print(f"dir_name: {dir_name}, uuid: {uuid}")
    print(f"get data status: {SERVER_INFO["ODM_URL"]}/task/{uuid}/info")
    result = requests.get(f"{SERVER_INFO["ODM_URL"]}/task/{uuid}/info")
    print(f"result: {result.json()}")
    if result.status_code == 200:
        # result에 error라는 key가 있을 경우, 준비중
        if "error" in result.json():
            return {
                "status": DATA_STATUS["ONPROGRESS"],
                "data": {"startedAt": "uploading", "uuid": uuid}
            }
        if result["status"]["code"] == ODM_STATUS["QUEUED"] or result["status"]["code"] == ODM_STATUS["RUNNING"]:
            return {
                "status": DATA_STATUS["ONPROGRESS"],
                "data": {"startedAt": get_time_from_timestamp(result["status"]["dateCreated"]),
                         "progress": result["progress"],
                         "uuid": uuid}
            }
        if result["status"]["code"] == ODM_STATUS["FAILED"] or result["status"]["code"] == ODM_STATUS["CANCELED"]:
            return {
                "status": DATA_STATUS["ERROR"],
                "data": {"errorLog": result["status"]["message"],
                         "uuid": uuid}
            }
        if result["status"]["code"] == ODM_STATUS["COMPLETED"]:
            return {
                "status": DATA_STATUS["DONE"],
                "data": {"finishedAt": get_time_from_timestamp(result["status"]["dateFinished"]), "uuid": uuid}
            }

    return {
        "status": DATA_STATUS["ERROR"],
        "data": {"errorLog": "Data not found", "uuid": uuid}
    }
