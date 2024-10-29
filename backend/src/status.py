import os
from datetime import datetime
import requests

from src.server_info import SERVER_INFO

from src.file_query import DATA_PATH, get_uuid_by_name

from src.utils import convert_time

DATA_STATUS = {
    "UPLOADING": 0,
    "READY": 1,
    "ONPROGRESS": 2,
    "DONE": 3,
    "ERROR": 4,
    "QUEUED": 5
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


def get_time_from_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def get_data_status_step1(dir_name: str) -> tuple[str, int, dict]:
    """

    :param dir_name:
    :return:
    """

    # 업로드 중인 데이터
    if "uploading.txt" in os.listdir(os.path.join(DATA_PATH, dir_name)):
        uploaded_time = os.path.getctime(os.path.join(DATA_PATH, dir_name))
        uploaded_time = datetime.fromtimestamp(uploaded_time)
        n_image = len(os.listdir(os.path.join(DATA_PATH, dir_name, "images")))
        return convert_time(uploaded_time), n_image, {
            "status": DATA_STATUS["UPLOADING"],
            "data": {"startedAt": convert_time(uploaded_time)}
        }

    # 존재하지 않는 파일
    if dir_name is None:
        print(f"Error: {dir_name} is not found")
        return "", 0, {
            "status": DATA_STATUS["ERROR"],
            "data": {"errorLog": "Data not found"}
        }

    data_path = os.path.join(DATA_PATH, dir_name)
    opencv_path = os.path.join(data_path, "opencv_output")
    image_path = os.path.join(data_path, "images")
    n_images = len(os.listdir(image_path))
    uploaded_time = os.path.getctime(data_path)
    uploaded_time = convert_time(datetime.fromtimestamp(uploaded_time))
    # 정합 전인 데이터
    # data_path에 opencv_output이라는 폴더가 존재하지 않으면 정합 전
    if not os.path.exists(opencv_path):
        return convert_time(uploaded_time), n_images, {
            "status": DATA_STATUS["READY"],
            "data": {"uploadedAt": uploaded_time}
        }

    # 정합 에러 데이터
    # data_path에 opencv_output이 존재하고, 그 폴더에 error.txt가 존재하면 정합 에러
    if os.path.exists(os.path.join(data_path, "opencv_output", "error.txt")):
        # 에러 로그를 읽어서 반환
        with open(os.path.join(data_path, "opencv_output", "error.txt"), "r") as f:
            error_log = f.read()
        return convert_time(uploaded_time), n_images, {
            "status": DATA_STATUS["ERROR"],
            "data": {"errorLog": error_log}
        }

    # 정합 중 혹은 완료 데이터
    n_cluster = 0
    n_completed = 0
    current_cluster = 0
    uploaded_time = os.path.getctime(os.path.join(opencv_path))
    uploaded_time = convert_time(datetime.fromtimestamp(uploaded_time))
    # data_path에 opencv_output이 존재하지만, opencv_output에 c로 시작하는 폴더가 존재하면 정합 중
    for opencv_file in os.listdir(opencv_path):
        if opencv_file.startswith("c_"):
            n_cluster = int(opencv_file.split('_')[1].split('.')[0])

        if opencv_file.startswith("opencv_"):
            n_completed += 1
            if current_cluster < int(opencv_file.split('_')[1].split('.')[0]):
                current_cluster = int(opencv_file.split('_')[1].split('.')[0])

    if n_cluster == 0:
        return convert_time(uploaded_time), n_images, {
            "status": DATA_STATUS["ONPROGRESS"],
            "data": {"startedAt": uploaded_time}
        }
    # 정합이 완료된 경우
    if n_completed == n_cluster or "flag.txt" in os.listdir(opencv_path):
        return convert_time(uploaded_time), n_images, {
            "status": DATA_STATUS["DONE"],
            "data": {"dataPath": data_path}
        }
    # 정합 실패
    elif n_completed < n_cluster and "flag.txt" in os.listdir(opencv_path):
        return convert_time(uploaded_time), n_images, {
            "status": DATA_STATUS["ERROR"],
            "data": {"errorLog": "Stitching failed partially"}
        }
    # 정합 중
    else:
        return convert_time(uploaded_time), n_images, {
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
    uploaded_time = get_time_from_timestamp(os.path.getctime(os.path.join(DATA_PATH, dir_name)))
    uploaded_time = convert_time(uploaded_time)
    if uuid is None:
        response = requests.post(f"{SERVER_INFO['ODM_URL']}/task/new/init", )
        uuid = response.json()["uuid"]

        data_path = os.path.join(DATA_PATH, dir_name)

        # data_path에 uuid_{uuid}.txt 파일 생성
        with open(os.path.join(data_path, f"uuid_{uuid}.txt"), "w") as f:
            f.write(f"Task is created in {datetime.now()}")

    if "uploading.txt" in os.listdir(os.path.join(DATA_PATH, dir_name)):
        uploaded_time = os.path.getctime(os.path.join(DATA_PATH, dir_name))
        uploaded_time = datetime.fromtimestamp(uploaded_time)
        n_image = len(os.listdir(os.path.join(DATA_PATH, dir_name, "images")))
        return {
            "status": DATA_STATUS["UPLOADING"],
            "data": {"startedAt": convert_time(uploaded_time)}
        }

    # step2_uploading이라는 파일이 존재하면, OnProgress
    if "step2_uploading" in os.listdir(os.path.join(DATA_PATH, dir_name)):
        started_at = get_time_from_timestamp(os.path.getctime(os.path.join(DATA_PATH, dir_name, "step2_uploading")))
        return {
            "status": DATA_STATUS["UPLOADING"],
            "data": {"startedAt": started_at, "uuid": uuid}
        }
    response = requests.get(f"{SERVER_INFO["ODM_URL"]}/task/{uuid}/info")
    if response.status_code != 200:
        return {
            "status": DATA_STATUS["ERROR"],
            "data": {"errorLog": "Data not found", "uuid": uuid}
        }

    response_json = response.json()
    if response.status_code == 200:
        # result에 error라는 key가 있을 경우, 준비중
        if "error" in response.json():
            return {
                "status": DATA_STATUS["READY"],
                "data": {"startedAt": "uploading", "uuid": uuid}
            }
        if response_json["status"]["code"] == ODM_STATUS["QUEUED"]:
            return {
                "status": DATA_STATUS["QUEUED"],
                "data": {"startedAt": get_time_from_timestamp(response_json["dateCreated"] // 1000),
                         "uuid": uuid}
            }

        if response_json["status"]["code"] == ODM_STATUS["RUNNING"]:
            return {
                "status": DATA_STATUS["ONPROGRESS"],
                "data": {"startedAt": get_time_from_timestamp(response_json["dateCreated"] // 1000),
                         "progress": response_json["progress"],
                         "uuid": uuid}
            }
        if response_json["status"]["code"] == ODM_STATUS["FAILED"] or response_json["status"]["code"] == ODM_STATUS[
            "CANCELED"]:
            return {
                "status": DATA_STATUS["ERROR"],
                "data": {"errorLog": response_json["message"],
                         "uuid": uuid}
            }
        if response_json["status"]["code"] == ODM_STATUS["COMPLETED"]:
            return {
                "status": DATA_STATUS["DONE"],
                "data": {"finishedAt": get_time_from_timestamp(
                    response_json["dateCreated"] // 1000 + response_json["processingTime"] // 1000), "uuid": uuid}
            }
        if response_json["status"]["code"] == ODM_STATUS["UPLOADING"]:
            return {
                "status": DATA_STATUS["UPLOADING"],
                "data": {"startedAt": uploaded_time, "uuid": uuid}
            }

    return {
        "status": DATA_STATUS["ERROR"],
        "data": {"errorLog": "Data not found", "uuid": uuid}
    }
