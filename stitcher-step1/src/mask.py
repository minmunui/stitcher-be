import numpy as np


def get_mask(image):
    channel_sum = np.sum(image, axis=2)
    mask = np.where(channel_sum > 3, 255, 0).astype(np.uint8)
    return mask

