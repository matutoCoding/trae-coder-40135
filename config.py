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

RECALL_STATUS_PENDING = "pending"
RECALL_STATUS_NOTIFIED = "notified"
RECALL_STATUS_IN_STORE = "in_store"
RECALL_STATUS_CLOSED = "closed"

RECALL_STATUS_LABELS = {
    RECALL_STATUS_PENDING: "未通知",
    RECALL_STATUS_NOTIFIED: "已通知",
    RECALL_STATUS_IN_STORE: "已到店处理",
    RECALL_STATUS_CLOSED: "已关闭",
}
RECALL_STATUS_COLORS = {
    RECALL_STATUS_PENDING: "#b71c1c",
    RECALL_STATUS_NOTIFIED: "#ef6c00",
    RECALL_STATUS_IN_STORE: "#1976d2",
    RECALL_STATUS_CLOSED: "#2e7d32",
}

PRIORITY_NORMAL = 0
PRIORITY_HIGH = 1

PRIORITY_LABELS = {
    PRIORITY_NORMAL: "普通",
    PRIORITY_HIGH: "优先",
}
PRIORITY_REASONS = ["返修", "预约", "VIP", "老客户", "其他"]


def ensure_dirs():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(PHOTO_DIR, exist_ok=True)
