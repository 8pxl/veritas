import json
import os
import sys
import tempfile
import time

import cv2
import numpy as np
from feat import Detector

# Lazy-load detector on first use
_detector = None


def _get_detector():
    global _detector
    if _detector is None:
        _detector = Detector(device="cuda")
    return _detector


# --- AU / Emotion column names ---
AU_COLS = [
    "AU01",
    "AU02",
    "AU04",
    "AU05",
    "AU06",
    "AU07",
    "AU09",
    "AU10",
    "AU11",
    "AU12",
    "AU14",
    "AU15",
    "AU17",
    "AU20",
    "AU23",
    "AU24",
    "AU25",
    "AU26",
    "AU28",
    "AU43",
]
EMOTION_COLS = [
    "anger",
    "disgust",
    "fear",
    "happiness",
    "sadness",
    "surprise",
    "neutral",
]
POSE_COLS = ["Pitch", "Roll", "Yaw"]


def extract_frames(video_path, fps=2, max_width=640):
    """Extract frames from video at target FPS, downscaled for speed.

    Returns list of (timestamp_sec, temp_jpg_path).
    """
    cap = cv2.VideoCapture(video_path)
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / video_fps

    step = 1.0 / fps
    timestamps = np.arange(0, duration, step)

    tmpdir = tempfile.mkdtemp(prefix="vidanalysis_")
    results = []

    for ts in timestamps:
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        if w > max_width:
            scale = max_width / w
            frame = cv2.resize(frame, (max_width, int(h * scale)))
        path = os.path.join(tmpdir, f"f_{ts:.2f}.jpg")
        cv2.imwrite(path, frame)
        results.append((ts, path))

    cap.release()
    return results, tmpdir


def detect_faces(frame_paths, batch_size=8):
    """Run py-feat Detector on a list of frame paths.

    Returns a DataFrame with AU, emotion, pose columns per face per frame.
    """
    detector = _get_detector()
    paths = [p for _, p in frame_paths]
    result = detector.detect_image(paths, batch_size=batch_size)
    return result


def extract_video_features(video_path, fps=2):
    """Full pipeline: extract frames → detect → aggregate features.

    Returns dict of per-frame AU/emotion data and summary statistics.
    """
    t0 = time.time()
    frames, tmpdir = extract_frames(video_path, fps=fps)
    t_extract = time.time() - t0

    t0 = time.time()
    detections = detect_faces(frames)
    t_detect = time.time() - t0

    # Clean up temp files
    for _, p in frames:
        try:
            os.remove(p)
        except OSError:
            pass
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass

    # Parse per-frame AU & emotion values
    n = len(detections)
    if n == 0:
        return {"error": "No faces detected", "frames_extracted": len(frames)}

    au_data = {}
    for col in AU_COLS:
        vals = detections[col].values.astype(float)
        au_data[col] = {
            "mean": float(np.nanmean(vals)),
            "std": float(np.nanstd(vals)),
            "max": float(np.nanmax(vals)),
        }

    emotion_data = {}
    for col in EMOTION_COLS:
        vals = detections[col].values.astype(float)
        emotion_data[col] = {
            "mean": float(np.nanmean(vals)),
            "std": float(np.nanstd(vals)),
        }

    pose_data = {}
    for col in POSE_COLS:
        vals = detections[col].values.astype(float)
        pose_data[col] = {
            "mean": float(np.nanmean(vals)),
            "std": float(np.nanstd(vals)),
        }

    # Dominant emotion per frame
    emotion_matrix = detections[EMOTION_COLS].values.astype(float)
    dominant_per_frame = [EMOTION_COLS[i] for i in np.argmax(emotion_matrix, axis=1)]
    emotion_counts = {e: dominant_per_frame.count(e) for e in EMOTION_COLS}

    return {
        "frames_extracted": len(frames),
        "faces_detected": n,
        "timing": {
            "frame_extraction_s": round(t_extract, 2),
            "detection_s": round(t_detect, 2),
            "total_s": round(t_extract + t_detect, 2),
        },
        "au": au_data,
        "emotions": emotion_data,
        "pose": pose_data,
        "dominant_emotion_counts": emotion_counts,
    }


# ============================================================
# Facial Confidence Score
# ============================================================


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _gaussian(value, center, sigma):
    return float(np.exp(-0.5 * ((value - center) / sigma) ** 2))


def compute_facial_confidence(video_path, fps=2):
    """Compute a facial expression confidence score in [0, 1].

    Components:
      - composure      (0.25): low anxiety AUs (AU01+AU04 worry, AU15 sadness,
                                AU20 fear, AU28 nervousness)
      - positive_affect (0.20): Duchenne smile (AU06+AU12), happiness emotion
      - emotional_stability (0.25): low variance in emotions across frames
      - gaze_stability  (0.15): steady head pose (low yaw/pitch variance)
      - neutrality      (0.15): high neutral emotion ratio
    """
    features = extract_video_features(video_path, fps=fps)
    if "error" in features:
        return {"confidence_score": 0.0, "error": features["error"]}

    au = features["au"]
    emo = features["emotions"]
    pose = features["pose"]
    counts = features["dominant_emotion_counts"]
    total = features["faces_detected"]

    # --- Component 1: Composure ---
    # Low anxiety/uncertainty AUs → confident
    # AU01 (inner brow raise), AU04 (brow lower) → worry
    # AU15 (lip corner depressor) → sadness
    # AU20 (lip stretch) → fear
    # AU28 (lip suck) → nervousness
    anxiety_score = (
        au["AU01"]["mean"] * 0.2
        + au["AU04"]["mean"] * 0.2
        + au["AU15"]["mean"] * 0.2
        + au["AU20"]["mean"] * 0.2
        + au["AU28"]["mean"] * 0.2
    )
    # anxiety_score in [0, 1]; lower is more composed
    composure = 1.0 - _clamp(anxiety_score)

    # --- Component 2: Positive affect ---
    # Duchenne smile: AU06 (cheek raiser) + AU12 (lip corner puller)
    smile_intensity = (au["AU06"]["mean"] + au["AU12"]["mean"]) / 2.0
    happiness_mean = emo["happiness"]["mean"]
    positive_affect = _clamp(0.5 * smile_intensity + 0.5 * happiness_mean)

    # --- Component 3: Emotional stability ---
    # Low variance across emotions = stable presence
    emotion_stds = [emo[e]["std"] for e in EMOTION_COLS]
    mean_emotion_std = float(np.mean(emotion_stds))
    # Typical range: 0.05 (very stable) to 0.3 (volatile)
    emotional_stability = _gaussian(mean_emotion_std, center=0.0, sigma=0.15)

    # --- Component 4: Gaze stability ---
    # Confident speakers maintain steady head pose
    yaw_std = pose["Yaw"]["std"]
    pitch_std = pose["Pitch"]["std"]
    # Low variance → stable; typical confident range: <5 degrees std
    gaze_stability = 0.5 * _gaussian(yaw_std, center=0.0, sigma=5.0) + 0.5 * _gaussian(
        pitch_std, center=0.0, sigma=5.0
    )

    # --- Component 5: Neutrality ---
    # High neutral fraction = composed, in-control demeanor
    neutral_ratio = counts.get("neutral", 0) / max(total, 1)
    # Blend with mean neutral emotion probability
    neutrality = 0.5 * neutral_ratio + 0.5 * emo["neutral"]["mean"]

    components = {
        "composure": round(composure, 4),
        "positive_affect": round(positive_affect, 4),
        "emotional_stability": round(emotional_stability, 4),
        "gaze_stability": round(gaze_stability, 4),
        "neutrality": round(neutrality, 4),
    }

    weights = {
        "composure": 0.25,
        "positive_affect": 0.20,
        "emotional_stability": 0.25,
        "gaze_stability": 0.15,
        "neutrality": 0.15,
    }

    score = sum(components[k] * weights[k] for k in weights)
    score = _clamp(score)

    return {
        "confidence_score": round(score, 4),
        "components": components,
        "weights": weights,
        "features": features,
    }


def _print_result(label, result):
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"  FACIAL CONFIDENCE SCORE: {result['confidence_score']:.4f}")
    print(f"{'=' * 60}")
    if "error" in result:
        print(f"  Error: {result['error']}")
        return

    feats = result["features"]
    print(
        f"  Timing: {feats['timing']['total_s']:.1f}s "
        f"(extract: {feats['timing']['frame_extraction_s']:.1f}s, "
        f"detect: {feats['timing']['detection_s']:.1f}s)"
    )
    print(
        f"  Frames: {feats['frames_extracted']} extracted, "
        f"{feats['faces_detected']} faces detected"
    )

    print(f"\n  Components:")
    for name, value in result["components"].items():
        w = result["weights"][name]
        bar = "#" * int(value * 20)
        print(f"    {name:25s}: {value:.4f}  [{bar:<20s}]  (w={w})")

    print(f"\n  Dominant emotions: {feats['dominant_emotion_counts']}")

    print(f"\n  Key AUs (mean):")
    for au_name in ["AU01", "AU04", "AU06", "AU12", "AU15", "AU20", "AU28"]:
        v = feats["au"][au_name]["mean"]
        print(f"    {au_name}: {v:.4f}")

    print(f"\n  Emotions (mean):")
    for e in EMOTION_COLS:
        v = feats["emotions"][e]["mean"]
        print(f"    {e:12s}: {v:.4f}")

    print(
        f"\n  Head pose std: Yaw={feats['pose']['Yaw']['std']:.2f}, "
        f"Pitch={feats['pose']['Pitch']['std']:.2f}"
    )


if __name__ == "__main__":
    files = sys.argv[1:] if len(sys.argv) > 1 else ["shorter.mp4"]

    results = {}
    for video_path in files:
        print(f"\nAnalyzing: {video_path} ...")
        results[video_path] = compute_facial_confidence(video_path, fps=2)
        _print_result(video_path, results[video_path])

    if len(results) > 1:
        print(f"\n{'=' * 60}")
        print("  SUMMARY")
        print(f"{'=' * 60}")
        for path, r in sorted(
            results.items(), key=lambda x: x[1]["confidence_score"], reverse=True
        ):
            s = r["confidence_score"]
            bar = "#" * int(s * 30)
            print(f"  {s:.4f}  [{bar:<30s}]  {path}")

    with open("facial_confidence_result.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nFull results saved to facial_confidence_result.json")
