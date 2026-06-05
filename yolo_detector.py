from pathlib import Path

import cv2

from counting_line import LineCrossingCounter

MODELS_DIR = Path(__file__).parent / "models"
TRACKER_CFG = Path(__file__).parent / "conveyor_tracker.yaml"


def resolve_model_path(model_file):
    """Prefer a pre-downloaded model under ./models/, else return the bare name
    so Ultralytics fetches it on first use."""
    local = MODELS_DIR / model_file
    return str(local) if local.exists() else model_file


def best_device():
    """Pick the fastest available inference backend."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


class YoloCounter:
    """YOLO11 detection + ByteTrack persistent IDs + line-crossing counter.

    Handles occlusion, object crossings, and class-aware counting far better
    than motion-based detection. Requires `ultralytics` installed.
    """

    name = "YOLO11 + ByteTrack"

    MODEL_SIZES = {
        "Custom (best-5)": "best-5.pt",
        "Nano (fastest)": "yolo11n.pt",
        "Small": "yolo11s.pt",
        "Medium (most accurate)": "yolo11m.pt",
    }

    def __init__(self, model_file="yolo11n.pt", imgsz=640):
        from ultralytics import YOLO  # deferred so MOG2 mode works without it

        self.model_path = resolve_model_path(model_file)
        self.model = YOLO(self.model_path)
        self.imgsz = imgsz
        self.device = best_device()

        # Warmup + fuse conv+bn layers for ~20% speed bump on CPU.
        try:
            self.model.fuse()
        except Exception:
            pass

        self.line_crosser = LineCrossingCounter()
        self.line_position = 0.5
        self.orientation = "horizontal"
        self.direction = "both"
        self.conf_threshold = 0.35
        self.iou_threshold = 0.5
        self.class_filter = None
        self.enhance_low_light = False
        self._clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

        self.on_count = None

    @property
    def total_count(self):
        return self.line_crosser.total

    def class_names(self):
        names = self.model.names
        if isinstance(names, dict):
            return names
        return {i: n for i, n in enumerate(names)}

    def resolve_class_filter(self, text):
        """Parse comma-separated class names/indices into a list of class indices."""
        text = (text or "").strip()
        if not text:
            self.class_filter = None
            return None, []
        names = self.class_names()
        name_to_idx = {v.lower(): k for k, v in names.items()}
        indices, unknown = [], []
        for token in text.split(","):
            tok = token.strip().lower()
            if not tok:
                continue
            if tok.isdigit():
                idx = int(tok)
                if idx in names:
                    indices.append(idx)
                else:
                    unknown.append(tok)
            elif tok in name_to_idx:
                indices.append(name_to_idx[tok])
            else:
                unknown.append(tok)
        self.class_filter = indices or None
        return indices, unknown

    def reset(self):
        self.line_crosser.reset()
        # Clear ByteTrack internal state so IDs restart fresh.
        if hasattr(self.model, "predictor") and self.model.predictor is not None:
            trackers = getattr(self.model.predictor, "trackers", None)
            if trackers:
                for t in trackers:
                    if hasattr(t, "reset"):
                        t.reset()

    def _enhance(self, frame):
        """CLAHE on L-channel (LAB) — lifts shadows, boosts local contrast.

        Big win for dark objects on a dark/black conveyor belt where the raw
        feed is low contrast and YOLO's feature extractor struggles.
        """
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self._clahe.apply(l)
        return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

    def process(self, frame):
        h, w = frame.shape[:2]
        if self.orientation == "horizontal":
            line_coord, axis_index = int(h * self.line_position), 1
            p1, p2 = (0, line_coord), (w, line_coord)
        else:
            line_coord, axis_index = int(w * self.line_position), 0
            p1, p2 = (line_coord, 0), (line_coord, h)

        infer_frame = self._enhance(frame) if self.enhance_low_light else frame

        kwargs = dict(
            persist=True,
            tracker=str(TRACKER_CFG) if TRACKER_CFG.exists() else "bytetrack.yaml",
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            imgsz=self.imgsz,
            device=self.device,
            half=(self.device != "cpu"),
            verbose=False,
        )
        if self.class_filter:
            kwargs["classes"] = self.class_filter

        results = self.model.track(infer_frame, **kwargs)
        r = results[0]

        tracked = {}
        tracked_spans = {}
        detections = []
        if r.boxes is not None and r.boxes.id is not None:
            ids = r.boxes.id.int().cpu().tolist()
            xyxy = r.boxes.xyxy.cpu().numpy()
            clses = r.boxes.cls.int().cpu().tolist()
            confs = r.boxes.conf.cpu().tolist()
            for tid, box, cls_idx, conf in zip(ids, xyxy, clses, confs):
                x1, y1, x2, y2 = box
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                tracked[tid] = (cx, cy)
                tracked_spans[tid] = (y1, y2) if axis_index == 1 else (x1, x2)
                detections.append((int(x1), int(y1), int(x2), int(y2),
                                   int(cls_idx), float(conf), int(tid)))

        counted_now = self.line_crosser.update(
            tracked, line_coord, axis_index, self.direction, self.on_count,
            spans=tracked_spans,
        )

        overlay = frame.copy()
        cv2.line(overlay, p1, p2, (0, 220, 255), 2, cv2.LINE_AA)

        names = self.class_names()
        for x1, y1, x2, y2, cls_idx, conf, tid in detections:
            counted = tid in self.line_crosser.counted
            color = (60, 120, 255) if counted else (80, 220, 120)
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
            label = f"#{tid} {names.get(cls_idx, '?')} {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(overlay, (x1, max(0, y1 - th - 6)),
                          (x1 + tw + 6, y1), color, -1)
            cv2.putText(overlay, label, (x1 + 3, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 1, cv2.LINE_AA)

        text = f"Count: {self.total_count}"
        cv2.putText(overlay, text, (16, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(overlay, text, (16, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    (40, 40, 40), 1, cv2.LINE_AA)

        return overlay, counted_now
