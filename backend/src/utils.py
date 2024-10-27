from datetime import datetime
from queue import Queue

def convert_time(time:datetime):
    if type(time) == str:
        if len(time.split('T')) == 2:
            time = time.split('T')[0] + ' ' + time.split('T')[1]
            time.split('.')[0]
            return time
        else:
            return time
    #YYYY-MM-DD HH:MM:SS
    return time.strftime("%Y-%m-%d %H:%M:%S")

task_queue = Queue()