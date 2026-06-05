import cv2
import numpy as np
from collections import OrderedDict

from counting_line import LineCrossingCounter


class CentroidTracker:
    """Assigns persistent IDs to detections across frames via nearest-neighbor matching."""

    def __init__(self, max_disappeared=25, max_distance=90):
        self.next_id = 0
        self.objects = OrderedDict()
        self.disappeared = OrderedDict()
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def register(self, centroid):
        self.objects[self.next_id] = centroid
        self.disappeared[self.next_id] = 0
        self.next_id += 1

    def deregister(self, obj_id):
        self.objects.pop(obj_id, None)
        self.disappeared.pop(obj_id, None)

    def update(self, centroids):
        if len(centroids) == 0:
            for obj_id in list(self.disappeared.keys()):
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared:
                    self.deregister(obj_id)
            return self.objects

        if len(self.objects) == 0:
            for c in centroids:
                self.register(c)
            return self.objects

        object_ids = list(self.objects.keys())
        object_centroids = np.array(list(self.objects.values()))
        input_centroids = np.array(centroids)

        D = np.linalg.norm(
            object_centroids[:, None] - input_centroids[None, :], axis=2
        )

        rows = D.min(axis=1).argsort()
        cols = D.argmin(axis=1)[rows]

        used_rows, used_cols = set(), set()
        for row, col in zip(rows, cols):
            if row in used_rows or col in used_cols:
                continue
            if D[row, col] > self.max_distance:
                continue
            obj_id = object_ids[row]
            self.objects[obj_id] = tuple(input_centroids[col])
            self.disappeared[obj_id] = 0
            used_rows.add(row)
            used_cols.add(col)

        for row in set(range(D.shape[0])) - used_rows:
            obj_id = object_ids[row]
            self.disappeared[obj_id] += 1
            if self.disappeared[obj_id] > self.max_disappeared:
                self.deregister(obj_id)

        for col in set(range(D.shape[1])) - used_cols:
            self.register(tuple(input_centroids[col]))

        return self.objects


class ObjectCounter:
    """Background-subtraction based counter. Fast, no deps, class-agnostic."""

    name = "Motion (MOG2)"

    def __init__(self):
        self.bg_subtractor = self._make_subtractor()
        self.tracker = CentroidTracker()
        self.line_crosser = LineCrossingCounter()

        self.line_position = 0.5
        self.orientation = "horizontal"
        self.direction = "both"
        self.min_area = 1500

        self.on_count = None
        self._warmup_frames = 0

    @property
    def total_count(self):
        return self.line_crosser.total

    @staticmethod
    def _make_subtractor():
        return cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=40, detectShadows=False
        )

    def reset(self):
        self.bg_subtractor = self._make_subtractor()
        self.tracker = CentroidTracker()
        self.line_crosser.reset()
        self._warmup_frames = 0

    def _mask(self, frame):
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        fg = self.bg_subtractor.apply(blurred)
        _, thresh = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
        thresh = cv2.dilate(thresh, kernel, iterations=2)
        return thresh

    def _detections(self, mask):
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        centroids, boxes = [], []
        for c in contours:
            if cv2.contourArea(c) < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            centroids.append((x + w // 2, y + h // 2))
            boxes.append((x, y, w, h))
        return centroids, boxes

    def process(self, frame):
        h, w = frame.shape[:2]

        if self.orientation == "horizontal":
            line_coord, axis_index = int(h * self.line_position), 1
            p1, p2 = (0, line_coord), (w, line_coord)
        else:
            line_coord, axis_index = int(w * self.line_position), 0
            p1, p2 = (line_coord, 0), (line_coord, h)

        mask = self._mask(frame)

        self._warmup_frames += 1
        if self._warmup_frames < 15:
            centroids, boxes = [], []
        else:
            centroids, boxes = self._detections(mask)

        tracked = self.tracker.update(centroids)

        counted_now = self.line_crosser.update(
            tracked, line_coord, axis_index, self.direction, self.on_count
        )

        overlay = frame.copy()
        cv2.line(overlay, p1, p2, (0, 220, 255), 2, cv2.LINE_AA)

        for (x, y, bw, bh) in boxes:
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (80, 220, 120), 2)

        for obj_id, centroid in tracked.items():
            color = (60, 120, 255) if obj_id in self.line_crosser.counted else (255, 160, 60)
            cx, cy = int(centroid[0]), int(centroid[1])
            cv2.circle(overlay, (cx, cy), 5, color, -1)
            cv2.putText(
                overlay, f"#{obj_id}", (cx + 8, cy - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
            )

        self._draw_count_badge(overlay)
        return overlay, counted_now

    def _draw_count_badge(self, img):
        text = f"Count: {self.total_count}"
        cv2.putText(img, text, (16, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(img, text, (16, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    (40, 40, 40), 1, cv2.LINE_AA)
