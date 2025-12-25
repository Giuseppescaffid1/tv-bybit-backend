import time
from engine import step

print("Worker started")

while True:
    try:
        step()
        time.sleep(0.35)
    except Exception as e:
        print("Worker error:", e)
        time.sleep(2)
