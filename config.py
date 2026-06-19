import sys
import os

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(APP_ROOT, "data", "leather_care.db")
PHOTO_DIR = os.path.join(APP_ROOT, "data", "photos")

MAX_SKIP_COUNT = 3

QUEUE_STATUS_WAITING = "waiting"
QUEUE_STATUS_CALLING = "calling"
QUEUE_STATUS_SERVING = "serving"
QUEUE_STATUS_SKIPPED = "skipped"
QUEUE_STATUS_DONE = "done"
QUEUE_STATUS_INVALID = "invalid"

MATERIAL_STATUS_ACTIVE = "active"
MATERIAL_STATUS_EXPIRED = "expired"
MATERIAL_STATUS_RECALL = "recall"


def ensure_dirs():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(PHOTO_DIR, exist_ok=True)
