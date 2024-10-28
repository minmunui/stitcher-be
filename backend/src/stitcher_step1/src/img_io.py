from datetime import datetime


def make_output_name() -> str:
    return f"{datetime.now().strftime('%Y%m%d%H%M%S')}"


def get_file_name(path: str) -> str:
    return path.split("/")[-1]
