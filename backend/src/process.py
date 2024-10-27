import os
import sys
from os import getcwd
from pathlib import Path

from threading import Thread

from backend.src.utils import task_queue

sys.path.append(str(Path(__file__).resolve().parents[2] / 'stitcher-step1'))

from main import run

def process_queue():
    while True:
        task_dir = task_queue.get()
        try:
            print(f'Processing {task_dir}')
            run(input_path=os.path.join(getcwd(),"datasets",task_dir))
        except Exception as e:
            print(f'Error processing {task_dir}: {e}')
        task_queue.task_done()



worker_thread = Thread(target=process_queue, daemon=True)
worker_thread.start()