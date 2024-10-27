import os

SERVER_INFO = {}
SERVER_INFO_FILE = "server_info.txt"
DATA_DIR = "../datasets"

def set_default_server_info():
    if not os.path.exists(SERVER_INFO_FILE):
        file = open(SERVER_INFO_FILE, "w")
        file.write("title!ODM Server\n")
        file.write("ODM_URL!http://localhost:8000")
        file.close()
    file = open(SERVER_INFO_FILE, "r")
    f_server = file.read()
    for line in f_server.split('\n'):
        if line == "":
            continue
        if line.startswith('#'):
            continue
        key, value = line.split("!")[0], line.split("!")[1]
        SERVER_INFO[key] = value
    file.close()

set_default_server_info()