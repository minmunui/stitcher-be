import argparse
import os
import shutil
import time

import cv2
from src.stitcher_step1.src.metadata.gps import align_images, plotClusteredPoints, getClusteredIndicesByNumber

ROT = {
    '0': "NO ROTATION",
    '-1': "DISCARD",
    '1': "ROTATE 180",
}

OPENCV_DIR_NAME = "opencv_output"


async def stitch_run(input_path: str,divide_threshold: int = 80, pano_conf: float = 1.0, scans: int = 1):
    output_path = os.path.join(input_path, OPENCV_DIR_NAME)
    shutil.rmtree(output_path, ignore_errors=True)
    # output_path가 존재하는지 출력 true or false
    os.makedirs(output_path, exist_ok=True)
    image_path = os.path.join(input_path, "images")
    n_cluster = len(os.listdir(image_path)) // divide_threshold + 1
    flag_path = os.path.join(output_path, f"c_{n_cluster}.txt")
    with open(flag_path, "w") as f:
        f.write("")

    try:
        stitch(input_path=input_path, pano_conf=pano_conf, scans=scans, n_cluster=n_cluster)
    except Exception as e:
        log_path = os.path.join(output_path, "error.txt")
        with open(log_path, "w") as f:
            f.write(str(e))


def stitch(input_path: str, pano_conf: float = 1.0, scans: int = 1, n_cluster: int = 1):
    image_path = os.path.join(input_path, "images")
    images, image_names, coordinates = align_images(dir_path=image_path)
    clustered_indices = getClusteredIndicesByNumber(coordinates, n_clusters=n_cluster)
    output_base = os.path.join(input_path, OPENCV_DIR_NAME)
    os.makedirs(output_base, exist_ok=True)

    plotClusteredPoints(coordinates, clustered_indices, output_path=os.path.join(output_base, "clustered.png"))

    for idx, clustered_index in enumerate(clustered_indices):
        clustered_images = [images[i] for i in clustered_index]
        clustered_image_names = [image_names[i] for i in clustered_index]
        cluster_output_base = os.path.join(output_base, f"cluster_{idx}")
        os.makedirs(cluster_output_base, exist_ok=True)

        for _idx, image_name in enumerate(clustered_image_names):
            cv2.imwrite(os.path.join(cluster_output_base, f"{_idx}_{image_name.split('\\')[-1]}"),
                        clustered_images[_idx])

        if scans == 1:
            stitcher = cv2.Stitcher.create(mode=cv2.STITCHER_SCANS)
        else:
            stitcher = cv2.Stitcher.create(mode=cv2.STITCHER_PANORAMA)

        stitcher.setPanoConfidenceThresh(pano_conf)

        try:
            status, stitched = stitcher.stitch(clustered_images)
        except Exception as e:
            raise Exception(f"Stitching step 1 failed | n_cluster : {n_cluster} | Error : {e}")

        if status == cv2.Stitcher_OK:
            cv2.imwrite(os.path.join(output_base, f"opencv_{idx}.jpg"), stitched)
        else:
            print("Stitching failed. Error code: ", status)
            raise Exception(f"Stitching step 1 failed | n_cluster : {n_cluster}")
    file = open(os.path.join(output_base, "flag.txt"), "w")
    file.write("1")
    file.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', type=str, help='input directory name', nargs='?', default="input")
    parser.add_argument('-p', '--pano_conf', type=float, help='panorama confidence', nargs='?', default=1.0)
    parser.add_argument('-r', '--scans', type=int, help='resize ratio', nargs='?', default=1)
    args = parser.parse_args()

    run(input_path=args.input, pano_conf=args.pano_conf, scans=args.scans)


if __name__ == '__main__':
    """
    Stitch images in the input directory sequentially..
    python main_sequential.py <input directory name>
    """
    print("=======================================")
    start_time = time.time()
    main()
    end_time = time.time()
    print(f"Time spent : {end_time - start_time}")
