import os

import exifread


def get_exif_data(img_dir: str = None, img_name: str = None, img_path: str = None):
    """
    Get exif data from image, if img_path is None, img_dir and img_name must be provided
    :param img_dir: image directory
    :param img_name:  image name
    :param img_path:  image path
    :return:
    """
    if img_dir != None and img_name != None:
        img_path = os.path.join(os.getcwd(), img_dir, img_name)
    elif img_path == None:
        raise Exception("img_path is None")

    with open(img_path, 'rb') as f:
        tags = exifread.process_file(f)
        return tags


def get_geotagging(exif_data):
    """
    Get geotagging data from exif data of image, insert exif data from get_exif_data()
    :param exif_data: exif data from image
    :return:
    """
    geotagging = {}
    for (key, val) in exif_data.items():
        if key.startswith('GPS'):
            geotagging[key] = val
    if not geotagging:
        raise ValueError("No EXIF geotagging found")
    return geotagging


def get_time_from_image(img_dir: str = None, img_name: str = None, img_path: str = None):
    """
    Get time from image, if img_path is None, img_dir and img_name must be provided
    :param img_dir: image directory
    :param img_name:  image name
    :param img_path:  image path
    :return:
    """
    if img_dir != None and img_name != None:
        img_path = os.path.join(os.getcwd(), img_dir, img_name)
    elif img_path == None:
        raise Exception("img_path is None")

    with open(img_path, 'rb') as f:
        tags = exifread.process_file(f)
        time = tags['Image DateTime']
        return time
