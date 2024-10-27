import math
import os
import cv2
import matplotlib.pyplot as plt
from cv2 import Mat
from numpy import ndarray
from tqdm import tqdm

from src.metadata.exif import get_geotagging
from src.metadata.time_read import get_exif_data, sort_names_by_date_time

DISCARD = -1
NORMAL = 0
ROTATED = 1

RANGE = 5.0


def get_decimal_from_dms(dms, ref):
    degrees = dms.values[0].num / dms.values[0].den
    minutes = dms.values[1].num / dms.values[1].den / 60.0
    seconds = dms.values[2].num / dms.values[2].den / 3600.0

    decimal = degrees + minutes + seconds
    if ref == 'S' or ref == 'W':
        decimal = -decimal
    return decimal


def get_coordinates(geotags):
    """
    Get latitude and longitude from geotags data gotten from get_geotagging()
    :param geotags:
    :return:
    """
    lat = get_decimal_from_dms(geotags['GPS GPSLatitude'], geotags['GPS GPSLatitudeRef'].printable)
    lon = get_decimal_from_dms(geotags['GPS GPSLongitude'], geotags['GPS GPSLongitudeRef'].printable)
    return lat, lon


def get_altitude(geotags):
    altitude = geotags.get('GPS GPSAltitude', None)
    altitude_ref = geotags.get('GPS GPSAltitudeRef', None)
    if altitude and altitude_ref:
        alt = altitude.values[0].num / altitude.values[0].den
        if altitude_ref.values[0] == 1:
            alt = -alt
        return alt
    raise ValueError("No altitude data found")


def get_gps_from_image(img_dir=None, img_name=None, img_path=None):
    """
    Get latitude, longitude, and altitude from image. If img_path is None, img_dir and img_name must be provided
    :param img_dir:
    :param img_name:
    :param img_path:
    :return:
    """
    exif_data = get_exif_data(img_dir, img_name, img_path)
    geotags = get_geotagging(exif_data)

    if geotags:
        lat, lon = get_coordinates(geotags)
        alt = get_altitude(geotags)
        return lat, lon, alt

    else:
        print()
        raise ValueError("No GPS data found")


def plot_coordinates(coordinates):
    lats, lons, alts = zip(*coordinates)
    plt.figure(figsize=(10, 6))
    plt.scatter(lons, lats, c='blue', marker='o')

    for i, (lat, lon, alt) in enumerate(coordinates):
        plt.text(lon, lat, f'{i}:{alt}', fontsize=12, ha='right')

    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title('Coordinates Plot')
    plt.grid(True)
    plt.show()


def get_direction(coord1: tuple[float, float], coord2: tuple[float, float]) -> tuple[float, float]:
    """
    Get direction from coord1 to coord2
    :param coord1:
    :param coord2:
    :return:
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    return dlat, dlon


def direction_to_angle(direction: tuple[float, float]) -> float:
    """
    Convert direction to angle
    :param direction:
    :return:
    """
    dlat, dlon = direction
    angle = (180 / math.pi) * (math.pi + math.pi / 2 - math.atan2(dlat, dlon))
    if angle < 0:
        return 360.0 + angle
    if angle > 360:
        return angle - 360.0
    return angle


def get_angel_between_coordinates(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    """
    Get angle between two coordinates
    :param coord1:
    :param coord2:
    :return:
    """
    direction = get_direction(coord1, coord2)
    return direction_to_angle(direction)


def get_angles(coordinates: list[tuple[float, float]]) -> list[float]:
    """
    Get angles between coordinates. coordinates must be list of (latitude, longitude)
    :param coordinates:
    :return:
    """
    angles = []
    for i in range(1, len(coordinates)):
        angle = get_angel_between_coordinates(coordinates[i - 1], coordinates[i])
        if i == 1:
            angles.append(angle)
        angles.append(angle)

    return angles


def to_360_angle(angle: float) -> float:
    """
    Convert angle from 0 to 360 degree
    :param angle:
    :return:
    """
    if angle < 0:
        return 360.0 + angle
    if angle > 360:
        return angle - 360.0
    return angle


def determine_rotation(standard: float, angle: float, threshold_range: float = RANGE) -> int:
    """
    Determine rotation of angle from standard angle. If angle is in threshold range, return NORMAL(0), REVERSED(1) if reversed, DISCARD(-1) if discarded
    :param standard:
    :param angle:
    :param threshold_range:
    :return:
    """
    if standard - threshold_range <= angle <= standard + threshold_range:
        return NORMAL
    elif to_360_angle(standard - threshold_range + 180) <= angle <= to_360_angle(standard + threshold_range + 180):
        return ROTATED
    else:
        return DISCARD


def to_180_angle(angle: float) -> float:
    """
    Convert angle from 0 to 180 degree
    :param angle:
    :return:
    """
    while not 0 <= angle <= 180:
        if angle < 0:
            angle += 180
        if angle > 180:
            angle -= 180
    return angle


def get_standard_angle(angles: list[float]) -> float:
    """
    Get standard angle from angles
    :param angles:
    :return:
    """
    scores = [0] * 180
    for angle in angles:
        if int(to_180_angle(angle))-1 < 0:
            scores[179] += 1
            scores[0] += 2
            scores[1] += 1
        elif int(to_180_angle(angle))+1 > 179:
            scores[178] += 1
            scores[179] += 2
            scores[0] += 1
        else:
            scores[int(to_180_angle(angle)) - 1] += 1
            scores[int(to_180_angle(angle))] += 2
            scores[int(to_180_angle(angle)) + 1] += 1
    return scores.index(max(scores))


def determine_rotation_angles(angles: list[float]) -> list[float]:
    """
    Determine rotation of angles from standard angle. If angle is in threshold range, return NORMAL(0), REVERSED(1) if reversed, DISCARD(-1) if discarded
    :param angles:
    :return:
    """
    print(f"angles : {angles}")
    standard = get_standard_angle(angles)
    print(f"standard : {standard}")
    results = []
    for angle in angles:
        results.append(determine_rotation(standard, angle))
    return results


def getClusteredIndicesByClustering(points, n_clusters, max_iterations=200):
    """
    Get clustered indices from points using clustering.

    :param max_iterations : int, maximum number of iterations
    :param points: list of (x, y) points
    :param n_clusters: int, number of clusters
    :return: list of indices
    """
    import numpy as np

    # points를 NumPy 배열로 변환 (이미 NumPy 배열이면 변환하지 않음)
    points_array = np.array(points)

    # 데이터의 개수
    n_points = points_array.shape[0]

    # 초기 중심점 선택 (데이터 중에서 무작위로 선택)
    np.random.seed(42)
    initial_centroids_indices = np.random.choice(n_points, n_clusters, replace=False)
    centroids = points_array[initial_centroids_indices]
    labels = np.zeros(n_points)

    for iteration in range(max_iterations):
        # 각 점에 대해 가장 가까운 중심점의 인덱스를 찾음
        distances = np.linalg.norm(points_array[:, np.newaxis] - centroids, axis=2)
        labels = np.argmin(distances, axis=1)

        # 새로운 중심점 계산
        new_centroids = np.array(
            [points_array[labels == k].mean(axis=0) if np.any(labels == k) else centroids[k] for k in
             range(n_clusters)])

        # 중심점의 변화량 확인
        if np.allclose(centroids, new_centroids):
            break  # 수렴하면 종료

        centroids = new_centroids

    # 각 클러스터에 속하는 점의 인덱스를 저장
    cluster_indices = [np.where(labels == k)[0] for k in range(n_clusters)]

    return cluster_indices

def getClusteredIndicesByNumber(points, n_clusters) -> list[list[int]]:
    """
    Get clustered indices from points, using force divide.

    :param max_iterations : int, maximum number of iterations
    :param points: list of (x, y) points
    :param n_clusters: int, number of clusters
    :return: list of list of indices
    """
    # points의 수를 세어서 2개로 나눔, 예를 들어 120개의 점이 있으면 60개씩 나눔 -> [0, 1, ..., 59], [60, 61, ..., 119] 121개의 점이 있으면 60개씩 나누고 1개가 남음 -> [0, 1, ..., 59], [60, 61, ..., 119, 120]
    n_points = len(points)
    n_points_per_cluster = n_points // n_clusters
    n_points_per_cluster_list = [n_points_per_cluster] * n_clusters
    for i in range(n_points % n_clusters):
        n_points_per_cluster_list[i] += 1

    # 각 클러스터에 속하는 점의 인덱스를 저장
    cluster_indices = []
    start = 0
    for n_points in n_points_per_cluster_list:
        cluster_indices.append(list(range(start, start + n_points)))
        start += n_points

    return cluster_indices


def plotClusteredPoints(points: list[tuple], clustered_indices: list[list[int]], output_path: str = None):
    """
    Plot clustered points.

    :param output_path:
    :param points: list of (x, y) points
    :param clustered_indices: list of indices
    """
    import matplotlib.pyplot as plt

    for i in range(len(clustered_indices)):
        cluster_points = [points[j] for j in clustered_indices[i]]
        cluster_points = list(zip(*cluster_points))
        plt.scatter(cluster_points[1], cluster_points[0])

    if output_path is not None:
        plt.savefig(output_path)
    else:
        plt.show()


def align_images(dir_path: str = None, image_paths: list[str] = None) -> tuple[
    list[Mat | ndarray], list[str] | None, list[tuple]]:
    """
    Align images from directory or image paths. rotate images if needed, discard images if needed, and return and save aligned images
    :param dir_path:
    :param image_paths:
    :return: aligned images, aligned image paths
    """

    if dir_path is not None:
        image_names = os.listdir(dir_path)
        image_paths = [os.path.join(dir_path, image_name) for image_name in image_names]
    elif image_paths is None:
        raise Exception("dir_path and image_paths are None")
    image_paths = sort_names_by_date_time(image_paths)

    coordinates = []
    images = []

    for image_path in tqdm(image_paths, desc="reading image coordinates"):
        coordinates.append(get_gps_from_image(img_path=image_path)[:2])

    angles = get_angles(coordinates)
    rotate = determine_rotation_angles(angles)

    discard_index = []

    # 계산된 회전값에 따라 이미지를 회전하거나 버림
    for i in tqdm(range(len(image_paths)), desc="refine images"):
        if rotate[i] == NORMAL:
            image = cv2.imread(image_paths[i])
            images.append(image)
        elif rotate[i] == ROTATED:
            image = cv2.imread(image_paths[i])
            image = cv2.rotate(image, cv2.ROTATE_180)
            images.append(image)
        else:
            discard_index.append(i)

    # 불필요한 이미지 제거
    for i in list(reversed(discard_index)):
        del image_paths[i]
        del coordinates[i]
        del angles[i]
        del rotate[i]

    return images, image_paths, coordinates

