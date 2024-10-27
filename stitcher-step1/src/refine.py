import os

import cv2
import numpy as np


def rotate_image(image, angle: float):
    """
    Rotate an image by a given angle.
    """
    image_center = tuple(np.array(image.shape[1::-1]) / 2)
    rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
    result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
    return result


def rotate_image_with_mask(image, angle: float):
    """
    Rotate an image by a given angle.
    """

    # 이미지의 높이와 너비를 얻기
    (h, w) = image.shape[:2]

    # 회전할 중심점 (이미지의 중앙)
    center = (w // 2, h // 2)

    # 회전 매트릭스를 생성 (30도, 확대/축소는 1로 유지)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    # 이미지의 새로운 경계 크기를 계산
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])

    # 새로운 경계 크기 계산
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))

    # 회전 후 이미지를 전체가 보이도록 하기 위해 이동
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]

    # 이미지 회전
    rotated_image = cv2.warpAffine(image, M, (new_w, new_h))

    mask = cv2.threshold(cv2.cvtColor(rotated_image, cv2.COLOR_BGR2GRAY), 1, 255, cv2.THRESH_BINARY)[1]

    return rotated_image, mask


def slice_image(image, slice_ratio):
    """
    Slice the image into a smaller image with the given ratio.
    """
    w, h = image.shape[1], image.shape[0]
    new_w, new_h = int(w * slice_ratio), int(h * slice_ratio)
    padding_w, padding_h = (w - new_w) // 2, (h - new_h) // 2
    return image[padding_h:padding_h + new_h, padding_w:padding_w + new_w]


def slice_all_images(src_path, dst_path, slice_ratio=0.8):
    """
    Slice all images in the given directory into smaller images with the given ratio.
    """
    current_path = os.getcwd()
    src_path = os.path.join(current_path, src_path)

    dst_path = os.path.join(current_path, dst_path)
    if not os.path.exists(dst_path):
        os.makedirs(dst_path)

    images_names = os.listdir(src_path)

    for i in range(len(images_names)):
        image_name = images_names[i]
        image_path = os.path.join(src_path, image_name)
        image = cv2.imread(image_path)
        sliced_image = slice_image(image, slice_ratio)
        cv2.imwrite(os.path.join(dst_path, image_name), sliced_image)

