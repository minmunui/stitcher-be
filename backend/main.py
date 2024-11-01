
import os
import threading
from datetime import datetime
from http.client import HTTPException
from os import listdir
from pathlib import Path

from fastapi import Form
from fastapi import FastAPI, UploadFile, File, APIRouter
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import subprocess
import requests

from src.stitcher_step1.main import OPENCV_DIR_NAME
from src.file_query import get_uuid_by_name
from src.process import run_coroutine_in_thread, request_odm_stitch
from src.server_info import SERVER_INFO_FILE, SERVER_INFO, DATA_DIR
from src.status import get_data_status_step1, get_data_status_step2
from src.stitcher_step1.main import stitch_run

import time

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'tiff'}

DIVIDE_THRESHOLD = 80

INIT_OPTIONS = {
    'name': (None, time.strftime("%Y%m%d-%H%M%S")),
    'options': (None, '[{"name":"fast-orthophoto","value":true}]'),
}

app = FastAPI()
router = APIRouter()
origins = [
    "http://localhost:5173",
    "http://localhost:8080",
    "http://localhost:59617",
    "http://127.0.0.1:59617",
    "http://0.0.0.0",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 허용할 Origin 목록
    allow_credentials=True,  # 쿠키 등 자격 증명 허용 여부
    allow_methods=["*"],  # 허용할 HTTP 메서드 목록
    allow_headers=["*"],  # 허용할 HTTP 헤더 목록
)


@router.get("/")
async def root():
    return {"message": "Hello World"}


@router.get("/server_info")
async def get_server_info():
    server_info = open(SERVER_INFO_FILE, "r")
    with server_info as f:
        info = f.read()
    server_info.close()
    server_data = {}
    for line in info.split("\n"):
        if line:
            if line == "":
                continue
            if line.startswith('#'):
                continue
            key, value = line.split("!")
            server_data[key] = value
    return JSONResponse(content=server_data, status_code=200)


@router.post("/server_info")
async def post_server_info(info: dict):
    for value in info.values():
        if len(value.split("!")) > 1:
            return JSONResponse(content={"error": "value cannot include '!'"}, status_code=400)
    for key in info.keys():
        if not key in ["title", "ODM_URL"]:
            return JSONResponse(content={"error": "Invalid key"}, status_code=400)
    server_info = open(SERVER_INFO_FILE, "w")

    if "title" not in info.keys():
        info["title"] = "ODM Server"
    if "ODM_URL" not in info.keys():
        info["ODM_URL"] = "http://localhost:5000"
    for key, value in info.items():
        print(f"{key}!{value}")
        server_info.write(f"{key}!{value}\n")
    server_info.seek(server_info.tell() - 1)
    server_info.close()
    return JSONResponse(content={"message": "Server info is updated"}, status_code=200)


@router.post("/stitch")
async def stitch(option: dict):
    step = option["step"]
    id = option["id"]
    size = DIVIDE_THRESHOLD
    if step == 1:
        size = option["size"]
        scan = option["scan"]
    print(f"step: {step}, id: {id}, size: {size}")
    if step == 1:
        input_path = Path(DATA_DIR) / id
        print(f"input_path: {input_path}")
        thread = threading.Thread(target=run_coroutine_in_thread, args=(stitch_run, input_path, size, scan))
        thread.start()
        return JSONResponse(content={"message": f"Task {id} is added to queue"}, status_code=200)
    elif step == 2:
        uuid = get_uuid_by_name(id)
        print(f"uuid: {uuid}")
        thread = threading.Thread(target=run_coroutine_in_thread, args=(request_odm_stitch, uuid, id))
        thread.start()
        return JSONResponse(content={"message": "Task is created"}, status_code=200)
    else:
        return JSONResponse(content={"error": "Invalid step"}, status_code=400)


@router.delete("/delete/{id}")
async def delete_data(id: str):
    try:
        uuid = get_uuid_by_name(id)
        requests.post(f"{SERVER_INFO['ODM_URL']}/task/remove", json={"uuid": uuid})
        data_path = Path(DATA_DIR) / id
        if data_path.exists():
            subprocess.run(['rm', '-rf', str(data_path)])
            return JSONResponse(content={"message": "Data is deleted"}, status_code=200)
        else:
            return JSONResponse(content={"error": "Data not found"}, status_code=404)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/reset/{id}")
async def reset_data(id: str):
    # 해당 폴더의 images와 uuid_로 시작하지 않는 파일 삭제
    data_path = Path(DATA_DIR) / id
    if data_path.exists():
        for file in listdir(data_path):
            if file.startswith("uuid_") or os.path.isdir(data_path / file):
                continue
            (data_path / file).unlink()

    opencv_dir = Path(DATA_DIR) / id / OPENCV_DIR_NAME
    if opencv_dir.exists():
        subprocess.run(['rm', '-rf', str(opencv_dir)])

    response = requests.post(f"{SERVER_INFO['ODM_URL']}/task/new/init", files=INIT_OPTIONS)
    print(f"response: {response.json()}")
    if response.status_code == 200:
        uuid = response.json()["uuid"]
        # 기존에 생성된 uuid 파일이 있다면 uuid를 얻음
        old_uuid = get_uuid_by_name(id)
        if old_uuid:
            requests.post(f"{SERVER_INFO['ODM_URL']}/task/remove", json={"uuid": old_uuid})
        uuid_files = [file for file in listdir(Path(DATA_DIR) / id) if file.startswith("uuid_")]
        for file in uuid_files:
            (Path(DATA_DIR) / id / file).unlink()
        with open(Path(DATA_DIR) / id / f"uuid_{uuid}.txt", "w") as f:
            f.write(f"Task is created in {datetime.now()}")
        return JSONResponse(content={"message": "Task is reset"}, status_code=200)
    else:
        return JSONResponse(content={"error": "Cannot reset task"}, status_code=500)


@router.get("/stitched_image/{id}/{step}")
async def stitched_image(id: str, step: int):
    if step == 1:
        image_dir = Path(DATA_DIR) / id / OPENCV_DIR_NAME
        if not image_dir.exists():
            raise HTTPException(status_code=404, detail="Image directory not found")
        image_files = [file.name for file in image_dir.iterdir() if
                       file.is_file() and file.suffix.lower() in ['.jpg', '.jpeg', '.png']]
        return JSONResponse(content={"url": image_files}, status_code=200)

    elif step == 2:
        download_path = SERVER_INFO["ODM_URL"] + "/task/" + get_uuid_by_name(id) + "/download/all.zip"
        return JSONResponse(content={"url": download_path}, status_code=200)
    else:
        return JSONResponse(content={"stitchedImage": "Invalid step"}, status_code=400)


@router.get("/stitched_image/download/{data_name}/{file_name}")
async def download_stitched_image(data_name: str, file_name: str):
    print(f"path = {Path(DATA_DIR) / data_name / OPENCV_DIR_NAME / file_name}")
    try:
        return FileResponse(Path(DATA_DIR) / data_name / OPENCV_DIR_NAME / file_name, filename=file_name,
                            media_type="image/jpeg")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image directory not found")


@router.get("/error_log/{id}/{step}")
async def get_status(id: str, step: int):
    if step == 1:
        try:
            with open(Path(DATA_DIR) / id / OPENCV_DIR_NAME / "error.txt", "r") as f:
                error_log = f.read()
        except FileNotFoundError:
            error_log = "No error log"

        return JSONResponse(content={"errorLog": error_log}, status_code=200)
    elif step == 2:
        status = get_data_status_step2(id)
        return JSONResponse(content={"errorLog": status["data"]["errorLog"]}, status_code=200)
    else:
        return JSONResponse(content={"errorLog": "Invalid step"}, status_code=400)


@router.get('/data')
async def get_data_list():
    print(f"INIT_OPTIONS : {INIT_OPTIONS}")
    try:
        # DATA_DIR이 존재하지 않을 경우 생성
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)
        # DATA_DIR 내의 폴더 목록을 가져옴
        folder_names = [name for name in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, name))]

        results = []
        name = ""
        for folder_name in folder_names:
            # print(folder_name)
            if not os.listdir(os.path.join(DATA_DIR, folder_name)):
                continue
            uploaded_time, n_image, status_1 = get_data_status_step1(folder_name)
            print(f"status_1: {status_1}")
            status_2 = get_data_status_step2(folder_name)
            print(f"status_2: {status_2}")
            if name != "":
                folder_name = name
            results.append({
                "name": folder_name,
                "time": uploaded_time,
                "size": n_image,
                "status_1": status_1,
                "status_2": status_2
            })
        return JSONResponse(content={"data": results}, status_code=200)

    except FileNotFoundError:
        return JSONResponse(content={"error": "Data folder not found"}, status_code=404)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# 허용된 파일인지 확인하는 함수
def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@router.post("/single_upload/{id}")
async def upload_file(id: str, file: UploadFile = File(...), total: int = Form(...)):
    if not id:
        raise HTTPException(status_code=422, detail="ID parameter is required")
    if not file:
        raise HTTPException(status_code=422, detail="File is required")

    return await save_file([file], id, total)


@router.post("/multiple_upload/{id}")
async def upload_file(id: str, files: list[UploadFile] = File(...), total: int = Form(...)):
    if not id:
        raise HTTPException(status_code=422, detail="ID parameter is required")
    if not files:
        raise HTTPException(status_code=422, detail="File is required")

    return await save_file(files, id, total)


async def save_file(files, id, total):
    print(f"files: {files}, id: {id}, total: {total}")
    # id가 -과 _외의 특수문자와 공백을 포함하고 있을 경우, 422 에러 반환
    if not all([c.isalnum() or c in ['-', '_'] for c in id]):
        raise HTTPException(status_code=422, detail="ID should contain only alphabets, numbers, - and _")

    upload_path = Path(DATA_DIR) / id / "images"
    upload_path.mkdir(parents=True, exist_ok=True)
    # 만약 os.path.join(DATA_DIR, id)에 uuid_로 시작하는 파일이 없다면, 새로운 task 생성
    if not any([file_name.startswith("uuid_") for file_name in listdir(Path(DATA_DIR) / id)]):

        response = requests.post(f"{SERVER_INFO['ODM_URL']}/task/new/init", files=INIT_OPTIONS)
        if response.status_code == 200:
            uuid = response.json()["uuid"]
            with open(Path(DATA_DIR) / id / f"uuid_{uuid}.txt", "w") as f:
                f.write(f"Task is created in {datetime.now()}")
    for file in files:
        file_location = upload_path / file.filename
        with open(file_location, "wb") as f:
            f.write(await file.read())
    current_files = len(list(upload_path.iterdir()))
    if current_files < total:
        with open(Path(DATA_DIR) / id / "uploading.txt", "w") as f:
            f.write("Uploading in progress")
    if current_files == total:
        uploading_file = Path(DATA_DIR) / id / "uploading.txt"
        if uploading_file.exists():
            uploading_file.unlink()
    return {"info": f"file is saved on {str(upload_path)}"}


app.include_router(router, prefix="/api")
