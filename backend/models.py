"""YOLO models are loaded once and shared."""
import threading
from ultralytics import YOLO
import config

_lock = threading.Lock()
_state = {}


def get_models():
    with _lock:
        if not _state:
            obj = YOLO(config.OBJ_WEIGHTS)
            pose = YOLO(config.POSE_WEIGHTS)
            ids = [i for i, n in obj.names.items() if n.lower() not in config.PERSON_NAMES]
            _state.update(obj=obj, pose=pose, ids=ids)
        return _state["obj"], _state["pose"], _state["ids"]


def ready():
    return bool(_state)
