from src.stitcher_step1.src.metadata.exif import get_exif_data


def time_to_seconds(time: str) -> int:
    """
    convert time to seconds the time format is "2021:07:23 12:34:56"
    :param time:
    :return: if time is "2021:07:23 12:34:56" then return 123456
    """
    return int(time.split(' ')[1].replace(':', ''))


def sort_names_by_date_time(names: list[str]) -> list[str]:
    exif_list = list(map(lambda x: get_date_time(get_exif_data(img_path=x)), names))
    combined = list(zip(names, exif_list))
    combined.sort(key=lambda x: time_to_seconds(x[1]))
    print(f"sorted names: {list(map(lambda x: x[0], combined))}")
    return list(map(lambda x: x[0], combined))


def get_date_time(exif_data: dict = None) -> str:
    return str(exif_data['Image DateTime'])


