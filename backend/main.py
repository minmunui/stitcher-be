import asyncio
import os
import sys
from contextlib import asynccontextmanager
from http.client import HTTPException
from os import listdir
from pathlib import Path

from fastapi import Form
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import requests

from src.file_query import get_uuid_by_name
from src.process import worker, task_queue
from src.server_info import SERVER_INFO_FILE, SERVER_INFO, DATA_DIR
from src.status import get_data_status_step1, get_data_status_step2

sys.path.append(str(Path(__file__).resolve().parents[1] / 'stitcher-step1'))

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'tiff'}

@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = asyncio.create_task(worker())
    yield
    worker_task.cancel()

# 순차적 실행하기

app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:59617",
    "http://127.0.0.1:59617",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 허용할 Origin 목록
    allow_credentials=True,  # 쿠키 등 자격 증명 허용 여부
    allow_methods=["*"],  # 허용할 HTTP 메서드 목록
    allow_headers=["*"],  # 허용할 HTTP 헤더 목록
)


@app.get("/")
async def root():
    return {"message": "Hello World"}
#
# @app.on_event("startup")
# async def startup_event():
#     await asyncio.create_task(task_worker())

@app.get("/server_info")
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


@app.post("/server_info")
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
        server_info.write(f"{key}!{value}\n")
    server_info.seek(server_info.tell() - 1)
    server_info.close()
    return JSONResponse(content={"message": "Server info is updated"}, status_code=200)


@app.post("/stitch")
async def stitch(option: dict):
    step = option["step"]
    id = option["id"]
    if step == 1:
        input_path = Path(DATA_DIR) / id / "images"
        print(f"input_path: {input_path}")
        task_queue.put(input_path)
        return JSONResponse(content={"message": f"Task {id} is added to queue"}, status_code=200)
    elif step == 2:
        print(f"stitch option : {option}")
        uuid = get_uuid_by_name(id)
        print(f"uuid: {uuid}")
        response = requests.post(f"{SERVER_INFO['ODM_URL']}/task/new/commit/{uuid}", json={"options": option})
        print(f"response: {response.json()}")
        return JSONResponse(content={"message": "Task is created"}, status_code=200)
    else:
        return JSONResponse(content={"error": "Invalid step"}, status_code=400)


@app.delete("/delete/{id}")
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


@app.get("/error/{id}/{step}")
async def get_status(id: str, step: int):
    if step == 1:
        uploaded_time, n_images, status = get_data_status_step1(id)
        return JSONResponse(content={"errorLog": status["data"]["errorLog"]}, status_code=200)
    elif step == 2:
        status = get_data_status_step2(id)
        return JSONResponse(content={"errorLog": status["data"]["errorLog"]}, status_code=200)
    else:
        return JSONResponse(content={"errorLog": "Invalid step"}, status_code=400)


@app.get('/data')
async def get_data_list():
    try:
        folder_names = [name for name in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, name))]
        results = []
        name = ""
        for folder_name in folder_names:
            folder_name = folder_name.split(";")[0]
            if len(folder_name.split(";")) > 1:
                name = folder_name.split(";")[0]
            uploaded_time, n_image, status_1 = get_data_status_step1(folder_name)
            status_2 = get_data_status_step2(folder_name)

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



@app.post("/single_upload/{id}")
async def upload_file(id: str, file: UploadFile = File(...), total: int = Form(...)):
    if not id:
        raise HTTPException(status_code=422, detail="ID parameter is required")
    if not file:
        raise HTTPException(status_code=422, detail="File is required")

    return await save_file([file], id, total)

@app.post("/multiple_upload/{id}")
async def upload_file(id: str, files: list[UploadFile] = File(...), total: int = Form(...)):
    if not id:
        raise HTTPException(status_code=422, detail="ID parameter is required")
    if not files:
        raise HTTPException(status_code=422, detail="File is required")

    return await save_file(files, id, total)


async def save_file(files, id, total):
    upload_path = Path(DATA_DIR) / id / "images"
    print(f"upload_path: {upload_path}")
    upload_path.mkdir(parents=True, exist_ok=True)
    # 만약 os.path.join(DATA_DIR, id)에 uuid_로 시작하는 파일이 없다면, 새로운 task 생성
    if not any([file_name.startswith("uuid_") for file_name in listdir(Path(DATA_DIR) / id)]):
        response = requests.post(f"{SERVER_INFO['ODM_URL']}/task/new/init")
        print(f"response: {response.json()}")
        if response.status_code == 200:
            uuid = response.json()["uuid"]
            with open(Path(DATA_DIR) / id / f"uuid_{uuid}.txt", "w") as f:
                f.write("Task is created")
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

# @app.post("/upload/{id}")
# async def upload_file(id: str, file: UploadFile = File(...)):
#     if not id:
#         raise HTTPException(status_code=422, detail="ID parameter is required")
#     if not file:
#         raise HTTPException(status_code=422, detail="File is required")
#     already_exist = False
#     uploaded = False
#     print(f"file_name: {file.filename}")
#
#     # 존재하는지 확인
#     for file_name in listdir(DATA_DIR):
#         if file_name.startswith(id):
#             if len(file_name.split(";")) > 1:
#                 already_exist = True
#                 uploaded = True
#                 id = file_name
#             if file_name == id:
#                 already_exist = True
#                 break
#
#     upload_path = Path(DATA_DIR) / id / "images"
#     if not already_exist:
#         upload_path.mkdir(parents=True, exist_ok=True)
#
#     file_location = upload_path / file.filename
#
#     # 파일 저장
#     with open(file_location, "wb") as f:
#         f.write(await file.read())
#
#     # 존재하지 않는다면, 새로운 uuid 생성하여 새로운 디렉토리 생성
#     if not uploaded:
#         response = requests.post(f"{SERVER_INFO['ODM_URL']}/task/new/init")
#         print(f"response: {response.json()}")
#
#         if response.status_code == 200:
#             uuid = response.json()["uuid"]
#             id = id + ";" + uuid
#             os.rename(upload_path, Path(DATA_DIR) / id / "images")
#         else:
#             return JSONResponse(content={"error": "Cannot create new task"}, status_code=500)
#
#     return {"info": f"file is saved on {str(file_location)}"}
