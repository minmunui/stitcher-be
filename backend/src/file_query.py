import os

from src.server_info import DATA_DIR

DATA_PATH = os.path.join(os.getcwd(), DATA_DIR)

def get_data_name_by_full_name(dir_uuid_name: str) -> str:
    return dir_uuid_name.split(';')[0]


def get_full_name_by_data_name(dir_name: str) -> str or None:
    """
    :param dir_name: 찾을 파일의 이름
    :return: 데이터 폴더의 이름을 반환
    """
    # DATA_PATH 경로에서 dir_name으로 시작하는 폴더를 찾아서 반환
    datalist = os.listdir(DATA_PATH)
    for data in datalist:
        if data.startswith(dir_name):
            return data
    return None


def get_uuid_by_name(dir_name: str) -> str or None:
    """
    :param dir_name: 찾을 파일의 이름
    :return: 데이터 폴더의 이름을 반환
    """
    datalist = os.listdir(DATA_PATH)
    for data in datalist:
        if data.startswith(dir_name):
            if len(data.split(';')) == 2:
                return data.split(';')[1]
            else:
                return None
