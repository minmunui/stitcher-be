import os
from os import listdir

from src.server_info import DATA_DIR

DATA_PATH = os.path.join(os.getcwd(), DATA_DIR)

def get_uuid_by_name(dir_name: str) -> str or None:
    """
    해당 이름을 가진 폴더 내부에 uuid_로 시작하는 파일을 찾아 uuid를 반환합니다.
    :param dir_name: 찾을 파일의 이름
    :return: 데이터 폴더의 이름을 반환
    """
    for file in listdir(os.path.join(DATA_PATH, dir_name)):
        if file.startswith('uuid_'):
            return file.split('_')[1].split('.')[0]
    return None

