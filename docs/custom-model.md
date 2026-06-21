# Custom model story (`best-5.pt`)

The app ships with a "Custom (best-5)" entry in the YOLO model picker
(`yolo_detector.py: MODEL_SIZES`). This page documents how a custom-trained
detector fits into the project — turning "I used YOLO" into "I trained and
deployed a model."

> **Note:** the weights are intentionally not committed (see `.gitignore`).
> Drop your trained `best-5.pt` into `./models/` and pick it in the UI, or run
> the API with `CVCOUNTER_ENGINE=yolo CVCOUNTER_MODEL=best-5.pt`.

## Why a custom model

The pretrained YOLO11 weights are trained on COCO's 80 everyday classes. A
conveyor line usually carries a *specific* set of SKUs (a particular bottle,
box, or part) that either aren't in COCO or are easily confused with each
other. A small custom model trained on a few hundred labelled frames of the
actual line:

- recognises the real product classes (per-class analytics become meaningful),
- is robust to the line's lighting, angle, and motion blur,
- can be tiny (nano backbone) yet more accurate *on this domain* than a large
  general model.

## Training recipe (template — fill in with your run)

```bash
# 1. Collect & label frames from the actual conveyor feed (e.g. with Roboflow
#    or Label Studio). Export in YOLO format.
# 2. Fine-tune a nano backbone:
yolo detect train \
    model=yolo11n.pt \
    data=conveyor.yaml \
    epochs=100 imgsz=640 batch=16 \
    name=best-5
# 3. The best checkpoint lands in runs/detect/best-5/weights/best.pt
cp runs/detect/best-5/weights/best.pt models/best-5.pt
```

| Field | Value |
|---|---|
| Base model | yolo11n.pt |
| Classes | _e.g._ bottle, cup, box, can, lid |
| Dataset size | _e.g._ 480 train / 60 val images |
| Epochs / imgsz | 100 / 640 |
| Validation mAP@50 | _fill in_ |
| Validation mAP@50-95 | _fill in_ |

## Evaluation harness (Roadmap Phase 9 stretch)

To report *counting* accuracy (not just detection mAP), run a labelled clip
through the headless counter and compare the produced tally to ground truth:

```bash
python headless.py --source clip.mp4 --engine yolo --model best-5.pt
```

Record the final `total` / per-class breakdown against the known counts to get
precision/recall of the end-to-end counter — a stronger signal than detector
metrics alone, because it folds in tracking and line-crossing logic.
