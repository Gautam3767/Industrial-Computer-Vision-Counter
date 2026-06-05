"""One-shot YOLO model downloader.

Run once: `python download_models.py`
Downloads yolo11n/s/m.pt into ./models/ so the app never re-downloads.
"""
import os
import sys
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
MODEL_FILES = ["yolo11n.pt", "yolo11s.pt", "yolo11m.pt"]


def main():
    MODELS_DIR.mkdir(exist_ok=True)
    os.chdir(MODELS_DIR)  # Ultralytics downloads into CWD

    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics not installed. Run: pip install ultralytics")
        sys.exit(1)

    for name in MODEL_FILES:
        target = MODELS_DIR / name
        if target.exists():
            size_mb = target.stat().st_size / 1024 / 1024
            print(f"✓ {name} already present ({size_mb:.1f} MB)")
            continue
        print(f"↓ Downloading {name}…")
        YOLO(name)  # triggers download into CWD (= MODELS_DIR)
        size_mb = target.stat().st_size / 1024 / 1024
        print(f"✓ {name} saved ({size_mb:.1f} MB)")

    print(f"\nAll models ready in: {MODELS_DIR}")
    print("You can now launch: python main.py")


if __name__ == "__main__":
    main()
