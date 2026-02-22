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
_fast_face_cascade = None
FACE_SCORE_THRESHOLD = 0.7
MAX_ANALYSIS_FRAMES = 16
_DETECTOR_CONFIG = {
    "face_model": "faceboxes",
    "landmark_model": "pfld",
    "au_model": "svm",
    "emotion_model": "svm",
    "facepose_model": "img2pose-c",
}


def _get_detector():
    global _detector
    if _detector is None:
        _detector = Detector(device="cpu", n_jobs=16, **_DETECTOR_CONFIG)
    return _detector


def _get_fast_face_cascade():
    global _fast_face_cascade
    if _fast_face_cascade is None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _fast_face_cascade = cv2.CascadeClassifier(cascade_path)
    return _fast_face_cascade


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


def extract_frames(video_path, fps=2, max_width=480):
    """Extract frames from video at target FPS, downscaled for speed.

    Returns list of (timestamp_sec, temp_jpg_path).
    """
    cap = cv2.VideoCapture(video_path)
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_step = max(1, int(round(video_fps / max(fps, 0.1))))

    tmpdir = tempfile.mkdtemp(prefix="vidanalysis_")
    results = []
    frame_idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % frame_step != 0:
            frame_idx += 1
            continue
        ts = frame_idx / video_fps
        h, w = frame.shape[:2]
        if w > max_width:
            scale = max_width / w
            frame = cv2.resize(frame, (max_width, int(h * scale)))
        path = os.path.join(tmpdir, f"f_{ts:.2f}.jpg")
        cv2.imwrite(path, frame)
        results.append((ts, path))
        frame_idx += 1

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


def detect_fast_face_bboxes(
    video_path, fps=15, max_width=320, min_neighbors=8, min_face_size=28
):
    """Fast bbox-only detector for dense per-frame face presence tracking."""
    cascade = _get_fast_face_cascade()
    cap = cv2.VideoCapture(video_path)
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_step = max(1, int(round(video_fps / max(fps, 0.1))))
    frame_idx = 0
    out = []

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % frame_step != 0:
            frame_idx += 1
            continue

        ts = frame_idx / video_fps
        h, w = frame.shape[:2]
        if w > max_width:
            scale = max_width / w
            frame = cv2.resize(frame, (max_width, int(h * scale)))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=min_neighbors,
            minSize=(min_face_size, min_face_size),
        )
        bboxes = []
        frame_area = float(max(gray.shape[0] * gray.shape[1], 1))
        for x, y, wb, hb in faces:
            if (wb * hb) / frame_area < 0.01:
                continue
            bboxes.append(
                {"x": float(x), "y": float(y), "w": float(wb), "h": float(hb)}
            )
        out.append(
            {"timestamp": float(ts), "face_count": len(bboxes), "bboxes": bboxes}
        )
        frame_idx += 1

    cap.release()
    return out


def _per_frame_face_bboxes(frame_paths, detections):
    """Build per-frame face bbox records, including frames with zero faces."""
    frame_map = {
        path: {"timestamp": float(ts), "face_count": 0, "bboxes": []}
        for ts, path in frame_paths
    }
    required_cols = {"FaceRectX", "FaceRectY", "FaceRectWidth", "FaceRectHeight"}
    if len(detections) > 0 and required_cols.issubset(set(detections.columns)):
        for _, row in detections.iterrows():
            key = row.get("input")
            record = frame_map.get(key)
            if record is None:
                continue
            x = float(row["FaceRectX"])
            y = float(row["FaceRectY"])
            w = float(row["FaceRectWidth"])
            h = float(row["FaceRectHeight"])
            if np.isnan(x) or np.isnan(y) or np.isnan(w) or np.isnan(h):
                continue
            if w <= 0 or h <= 0:
                continue
            bbox = {
                "x": round(x, 2),
                "y": round(y, 2),
                "w": round(w, 2),
                "h": round(h, 2),
            }
            record["bboxes"].append(bbox)

    out = []
    for ts, path in frame_paths:
        r = frame_map[path]
        r["face_count"] = len(r["bboxes"])
        out.append(r)
    return out


def _has_face_near_timestamp(face_timestamps, ts, tolerance=0.12):
    for fts in face_timestamps:
        if abs(fts - ts) <= tolerance:
            return True
    return False


def _downsample_frames(frames, max_frames=MAX_ANALYSIS_FRAMES):
    if len(frames) <= max_frames:
        return frames
    step = max(1, int(np.ceil(len(frames) / max_frames)))
    return frames[::step][:max_frames]


def _filter_detections_with_face_threshold(detections, threshold=FACE_SCORE_THRESHOLD):
    if len(detections) == 0:
        return detections
    required_cols = ["FaceRectX", "FaceRectY", "FaceRectWidth", "FaceRectHeight"]
    mask = np.ones(len(detections), dtype=bool)
    for col in required_cols:
        if col in detections.columns:
            vals = detections[col].astype(float).values
            mask &= np.isfinite(vals)
    if "FaceRectWidth" in detections.columns:
        mask &= detections["FaceRectWidth"].astype(float).values > 0
    if "FaceRectHeight" in detections.columns:
        mask &= detections["FaceRectHeight"].astype(float).values > 0
    if "FaceScore" in detections.columns:
        mask &= detections["FaceScore"].fillna(0).astype(float).values >= threshold
    return detections.loc[mask]


def extract_video_features(
    video_path, analysis_fps=2, bbox_fps=15, face_score_threshold=FACE_SCORE_THRESHOLD
):
    """Full pipeline: extract frames → detect → aggregate features.

    Returns dict of per-frame AU/emotion data and summary statistics.
    """
    t0 = time.time()
    per_frame_boxes = detect_fast_face_bboxes(video_path, fps=bbox_fps)
    t_bbox = time.time() - t0
    frames_with_faces = sum(1 for f in per_frame_boxes if f["face_count"] > 0)
    no_face_frames = len(per_frame_boxes) - frames_with_faces
    face_timestamps = [f["timestamp"] for f in per_frame_boxes if f["face_count"] > 0]

    t0 = time.time()
    frames, tmpdir = extract_frames(video_path, fps=analysis_fps)
    frames_for_analysis = [
        (ts, p) for ts, p in frames if _has_face_near_timestamp(face_timestamps, ts)
    ]
    frames_for_analysis = _downsample_frames(frames_for_analysis, MAX_ANALYSIS_FRAMES)
    t_extract = time.time() - t0

    t0 = time.time()
    detections = (
        detect_faces(frames_for_analysis, batch_size=16) if frames_for_analysis else []
    )
    if len(detections):
        detections = _filter_detections_with_face_threshold(
            detections, threshold=face_score_threshold
        )
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

    n = len(detections) if hasattr(detections, "__len__") else 0
    if n == 0:
        return {
            "error": "No faces detected",
            "frames_extracted": len(per_frame_boxes),
            "analysis_frames_extracted": len(frames),
            "analysis_frames_selected": len(frames_for_analysis),
            "bbox_fps": bbox_fps,
            "analysis_fps": analysis_fps,
            "face_score_threshold": face_score_threshold,
            "frames_with_faces": frames_with_faces,
            "no_face_frames": no_face_frames,
            "faces_detected": 0,
            "per_frame_face_bboxes": per_frame_boxes,
            "timing": {
                "bbox_detection_s": round(t_bbox, 2),
                "frame_extraction_s": round(t_extract, 2),
                "detection_s": round(t_detect, 2),
                "total_s": round(t_bbox + t_extract + t_detect, 2),
            },
        }

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
        "frames_extracted": len(per_frame_boxes),
        "analysis_frames_extracted": len(frames),
        "analysis_frames_selected": len(frames_for_analysis),
        "bbox_fps": bbox_fps,
        "analysis_fps": analysis_fps,
        "face_score_threshold": face_score_threshold,
        "frames_with_faces": frames_with_faces,
        "no_face_frames": no_face_frames,
        "faces_detected": n,
        "per_frame_face_bboxes": per_frame_boxes,
        "timing": {
            "bbox_detection_s": round(t_bbox, 2),
            "frame_extraction_s": round(t_extract, 2),
            "detection_s": round(t_detect, 2),
            "total_s": round(t_bbox + t_extract + t_detect, 2),
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
    features = extract_video_features(
        video_path,
        analysis_fps=fps,
        bbox_fps=15,
        face_score_threshold=FACE_SCORE_THRESHOLD,
    )
    if "error" in features:
        return {
            "confidence_score": 0.0,
            "error": features["error"],
            "features": features,
        }

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
        f"(bbox: {feats['timing'].get('bbox_detection_s', 0.0):.1f}s, "
        f"extract: {feats['timing']['frame_extraction_s']:.1f}s, "
        f"detect: {feats['timing']['detection_s']:.1f}s)"
    )
    print(
        f"  Frames: {feats['frames_extracted']} extracted, "
        f"{feats['frames_with_faces']} with faces, "
        f"{feats['no_face_frames']} without faces, "
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
        results[video_path] = compute_facial_confidence(video_path, fps=5)
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
