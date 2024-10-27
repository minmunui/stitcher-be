import os
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import requests

from src.server_info import SERVER_INFO_FILE, SERVER_INFO, DATA_DIR
from src.utils import task_queue
from src.status import get_data_status_step1, get_data_status_step2, get_uuid_by_name, \
    get_full_name_by_data_name

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'tiff'}


app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:59617",
    "http://127.0.0.1:59617",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # 허용할 Origin 목록
    allow_credentials=True,           # 쿠키 등 자격 증명 허용 여부
    allow_methods=["*"],              # 허용할 HTTP 메서드 목록
    allow_headers=["*"],              # 허용할 HTTP 헤더 목록
)

@app.get("/")
async def root():
    return {"message": "Hello World"}


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
    print(f"server_data: {server_data}")
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


@app.get("/dongjin")
async def audio_inference(
):
    result = subprocess.run(['docker', 'run', 'hello-world'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    str_stdout = result.stdout.decode('utf-8')
    list_stdout = list(str_stdout.split())

    return JSONResponse({"output": list_stdout})


@app.post("/stitch/{id}/{step}")
async def stitch(id: str, step: int, option: dict):
    if step == 1:
        task_queue.put(id)
        return JSONResponse(content={"message": "Task is added to queue"}, status_code=200)
    elif step == 2:
        uuid = get_uuid_by_name(id)
        requests.post(f"{SERVER_INFO['ODM_URL']}/task/new/commit/{uuid}", json={"options": option})
        return JSONResponse(content={"message": "Task is created"}, status_code=200)
    else:
        return JSONResponse(content={"error": "Invalid step"}, status_code=400)


@app.delete("/delete/{id}")
async def delete_data(id: str):
    try:
        uuid = get_uuid_by_name(id)
        full_name = get_full_name_by_data_name(id)
        requests.post(f"{SERVER_INFO['ODM_URL']}/task/remove", json={"uuid": uuid})
        data_path = Path(DATA_DIR) / full_name
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
        for folder_name in folder_names:
            name = folder_name
            uploaded_time, n_image, status_1 = get_data_status_step1(folder_name)
            status_2 = get_data_status_step2(folder_name)

            results.append({
                "name": name,
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


#
# @app.post("/upload")
# async def upload_file(file: UploadFile = File(...)):
#     # 파일 이름이 비어있는 경우
#     if not file.filename:
#         raise HTTPException(status_code=400, detail="선택된 파일이 없습니다")
#
#     # 파일 확장자 확인
#     if not allowed_file(file.filename):
#         raise HTTPException(status_code=400, detail="허용되지 않는 파일 형식입니다")
#
#     # 안전한 파일 이름 설정
#     filename = file.filename
#     save_path = UPLOAD_FOLDER / filename
#
#     # 업로드 폴더가 없으면 생성
#     UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
#
#     # 파일 저장
#     with open(save_path, "wb") as buffer:
#         buffer.write(await file.read())
#
#     return JSONResponse(content={"message": "파일이 성공적으로 업로드되었습니다"}, status_code=200)


@app.post("/upload/{id}")
async def upload_file(id: str, file: UploadFile = File(...)):
    # 저장할 디렉토리 설정 (예: dataset/{id}/images)
    upload_path = Path(DATA_DIR) / id / "images"
    upload_path.mkdir(parents=True, exist_ok=True)  # 디렉토리가 없으면 생성

    # 파일 경로 설정
    file_location = upload_path / file.filename

    # 파일 저장
    with open(file_location, "wb") as f:
        f.write(await file.read())

    return {"info": f"file is saved on {str(file_location)}"}

