from datetime import datetime
from queue import Queue

def convert_time(time:datetime):
    #YYYY-MM-DD HH:MM:SS
    return time.strftime("%Y-%m-%d %H:%M:%S")

task_queue = Queue()