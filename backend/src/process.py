import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2] / 'stitcher-step1'))

task_queue = asyncio.Queue()

async def worker():
    while True:
        input_path = await task_queue.get()
        print(f"Processing {input_path}")
        try:
            print(f"Processing {input_path}")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, stitch_run, input_path)
        except Exception as e:
            print(f"Error processing {input_path}: {e}")
        finally:
            task_queue.task_done()

