import subprocess
import json
import tempfile
from groq import Groq
import librosa
import numpy as np
import parselmouth
from parselmouth.praat import call
import os
from dotenv import load_dotenv

load_dotenv()


def extract_pitch_features(audio_path, time_step=0.01):
    snd = parselmouth.Sound(audio_path)
    pitch = call(snd, "To Pitch", time_step, 75, 600)

    pitch_values = pitch.selected_array["frequency"]
    voiced = pitch_values[pitch_values > 0]

    if len(voiced) == 0:
        return {
            "f0_mean": 0.0,
            "f0_std": 0.0,
            "f0_range": 0.0,
            "f0_median": 0.0,
            "voiced_fraction": 0.0,
        }

    return {
        "f0_mean": float(np.mean(voiced)),
        "f0_std": float(np.std(voiced)),
        "f0_range": float(np.max(voiced) - np.min(voiced)),
        "f0_median": float(np.median(voiced)),
        "voiced_fraction": float(len(voiced) / len(pitch_values)),
    }


def extract_voice_quality(audio_path):
    snd = parselmouth.Sound(audio_path)

    point_process = call(snd, "To PointProcess (periodic, cc)", 75, 600)

    # Jitter/shimmer need enough voiced periods — guard against empty PointProcess
    try:
        n_points = call(point_process, "Get number of points")
    except Exception:
        n_points = 0

    if n_points < 3:
        jitter_local = 0.0
        shimmer_local = 0.0
    else:
        try:
            jitter_local = call(
                point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3
            )
        except Exception:
            jitter_local = 0.0
        try:
            shimmer_local = call(
                [snd, point_process],
                "Get shimmer (local)",
                0,
                0,
                0.0001,
                0.02,
                1.3,
                1.6,
            )
        except Exception:
            shimmer_local = 0.0

    try:
        harmonicity = call(snd, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
        hnr = call(harmonicity, "Get mean", 0, 0)
    except Exception:
        hnr = 0.0

    return {
        "jitter": float(jitter_local) if not np.isnan(jitter_local) else 0.0,
        "shimmer": float(shimmer_local) if not np.isnan(shimmer_local) else 0.0,
        "hnr": float(hnr) if not np.isnan(hnr) else 0.0,
    }


def transcribe(path: str):
    client = Groq(api_key=os.getenv("OPENAI_API_KEY"))
    with open(path, "rb") as f:
        r = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
        )
    return r.to_dict()


def extract_temporal_features(result: dict):
    words = []

    # Groq Whisper puts words at the top level; OpenAI nests them in segments
    raw_words = result.get("words", [])
    if not raw_words:
        for segment in result.get("segments", []):
            raw_words.extend(segment.get("words", []))

    for word in raw_words:
        words.append(
            {
                "word": word["word"].strip(),
                "start": word["start"],
                "end": word["end"],
            }
        )

    if len(words) < 2:
        return {
            "speech_rate_wpm": 0.0,
            "pause_count": 0,
            "pause_mean_duration": 0.0,
            "pause_rate": 0.0,
            "filler_rate_per_min": 0.0,
            "articulation_ratio": 0.0,
        }

    total_duration = words[-1]["end"] - words[0]["start"]
    if total_duration <= 0:
        return {
            "speech_rate_wpm": 0.0,
            "pause_count": 0,
            "pause_mean_duration": 0.0,
            "pause_rate": 0.0,
            "filler_rate_per_min": 0.0,
            "articulation_ratio": 0.0,
        }

    speech_rate = len(words) / (total_duration / 60)

    pauses = []
    for i in range(1, len(words)):
        gap = words[i]["start"] - words[i - 1]["end"]
        if gap > 0.15:
            pauses.append(gap)

    fillers = {
        "uh",
        "um",
        "er",
        "ah",
        "like",
        "you know",
        "basically",
        "maybe",
        "probably",
        "guess",
        "somehow",
    }
    filler_count = sum(1 for w in words if w["word"].lower() in fillers)
    filler_rate = filler_count / (total_duration / 60)

    return {
        "speech_rate_wpm": speech_rate,
        "pause_count": len(pauses),
        "pause_mean_duration": float(np.mean(pauses)) if pauses else 0.0,
        "pause_rate": len(pauses) / (total_duration / 60),
        "filler_rate_per_min": filler_rate,
        "articulation_ratio": sum(w["end"] - w["start"] for w in words)
        / total_duration,
    }


def extract_energy_features(audio, sr, frame_length=2048, hop_length=512):
    rms = librosa.feature.rms(
        y=audio, frame_length=frame_length, hop_length=hop_length
    )[0]

    mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13, hop_length=hop_length)

    return {
        "energy_mean": float(np.mean(rms)),
        "energy_std": float(np.std(rms)),
        "energy_range": float(np.max(rms) - np.min(rms)),
        "mfcc_means": np.mean(mfccs, axis=1).tolist(),
        "mfcc_stds": np.std(mfccs, axis=1).tolist(),
    }


def analyze_audio_windows(audio_path, words, window_sec=30, step_sec=10):
    import soundfile as sf

    audio, sr = librosa.load(audio_path, sr=16000)
    results = []
    duration = len(audio) / sr
    start = 0

    while start + window_sec <= duration:
        end = start + window_sec

        start_sample = int(start * sr)
        end_sample = int(end * sr)
        window_audio = audio[start_sample:end_sample]

        # Use a proper temp file that gets cleaned up
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            sf.write(tmp.name, window_audio, sr)

            features = {}
            features.update(extract_pitch_features(tmp.name))
            features.update(extract_voice_quality(tmp.name))
            features.update(extract_energy_features(window_audio, sr))
            features["timestamp_start"] = start
            features["timestamp_end"] = end

        results.append(features)
        start += step_sec

    return results


# ============================================================
# Confidence Score Compositing
# ============================================================


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _normalize_to_baseline(value, baseline):
    """Ratio of value to baseline, clamped to [0, 2] then mapped to [0, 1].
    Returns 0 when value == 0, 1 when value == baseline, >1 when value > baseline."""
    if baseline <= 0:
        return 0.0
    return _clamp(value / baseline, 0.0, 2.0) / 2.0  # -> [0, 1]


def _gaussian_normalize(value, center, sigma):
    """Bell-curve around `center`. Returns 1.0 at center, falls off with sigma."""
    return float(np.exp(-0.5 * ((value - center) / sigma) ** 2))


def _normalize_ratio(value, max_val):
    """Linear normalize into [0, 1] given a known max."""
    if max_val <= 0:
        return 0.0
    return _clamp(value / max_val)


def compute_confidence_score(audio_path):
    """
    Extract all acoustic features from an audio file and composite them
    into a single confidence score in [0, 1].

    Components & weights:
      - pitch_stability  (0.20) : speaker-normalized pitch control (CV + range ratio)
      - speech_rate      (0.15) : moderate WPM ~ 150 is confident
      - pause_fluency    (0.25) : few + short pauses = confident; many long pauses = hesitant
      - filler_control   (0.25) : fewer fillers = more confident
      - voice_quality    (0.15) : higher HNR, lower jitter/shimmer

    Returns dict with score, components, derived metrics, and raw features.
    """
    audio, sr = librosa.load(audio_path, sr=16000)

    # --- Extract raw features ---
    pitch_feats = extract_pitch_features(audio_path)
    voice_qual = extract_voice_quality(audio_path)
    energy_feats = extract_energy_features(audio, sr)

    transcript = transcribe(audio_path)
    temporal_feats = extract_temporal_features(transcript)

    features = {}
    features.update(pitch_feats)
    features.update(voice_qual)
    features.update(energy_feats)
    features.update(temporal_feats)

    # --- Derived speaker-normalized metrics ---
    f0_mean = features["f0_mean"]
    # Coefficient of variation: speaker-independent pitch stability
    pitch_cv = features["f0_std"] / f0_mean if f0_mean > 0 else 1.0
    # Range ratio: how wide the pitch swings relative to speaker's register
    range_ratio = features["f0_range"] / f0_mean if f0_mean > 0 else 5.0

    # --- Compute component scores ---

    # 1) Pitch stability: blend of CV (40%) and range control (60%)
    #    CV ~ 0.15 is controlled variation; range_ratio ~ 1.5 is normal
    #    Earnings-call CEO: CV=0.34, range=4.58 → unstable under pressure
    #    YC CEO: CV=0.26, range=2.13 → expressive but controlled
    pitch_stability = 0.4 * _gaussian_normalize(
        pitch_cv, center=0.25, sigma=0.15
    ) + 0.6 * _gaussian_normalize(range_ratio, center=2.5, sigma=1.5)

    # 2) Speech rate: Gaussian around 150 WPM, tighter sigma to reward
    #    speakers closer to the confident center
    speech_rate = _gaussian_normalize(
        features["speech_rate_wpm"], center=150.0, sigma=25.0
    )

    # 3) Pause fluency: rate (40%) + mean duration (60%)
    #    Short deliberate pauses (0.25s) = confident; long hesitation (0.9s) = not
    #    Weight duration penalty by pause repetition so a single long pause
    #    in a short clip isn't penalized as harshly as a pattern of many
    pause_rate_score = _gaussian_normalize(
        features["pause_rate"], center=5.0, sigma=4.0
    )
    duration_raw = _gaussian_normalize(
        features["pause_mean_duration"], center=0.25, sigma=0.35
    )
    # Repetition factor: 0 pauses → no penalty; 3+ pauses → full penalty
    rep_factor = _clamp(features["pause_count"] / 3.0)
    duration_score = 1.0 - rep_factor * (1.0 - duration_raw)
    pause_fluency = 0.4 * pause_rate_score + 0.6 * duration_score

    # 4) Filler control: Gaussian centered at 0 fillers/min
    #    sigma=1.5 since filler set now includes hedge words (maybe, probably)
    filler_control = _gaussian_normalize(
        features["filler_rate_per_min"], center=0.0, sigma=1.5
    )

    # 5) Voice quality: realistic baselines for non-studio recordings
    #    HNR max ~15 dB (not 25 dB studio), shimmer max ~0.15, jitter max ~0.03
    voice_quality = (
        _normalize_ratio(features["hnr"], 15.0) * 0.50
        + (1.0 - _normalize_ratio(features["jitter"], 0.03)) * 0.25
        + (1.0 - _normalize_ratio(features["shimmer"], 0.15)) * 0.25
    )

    components = {
        "pitch_stability": pitch_stability,
        "speech_rate": speech_rate,
        "pause_fluency": pause_fluency,
        "filler_control": filler_control,
        "voice_quality": voice_quality,
    }

    weights = {
        "pitch_stability": 0.20,
        "speech_rate": 0.15,
        "pause_fluency": 0.25,
        "filler_control": 0.25,
        "voice_quality": 0.15,
    }

    score = sum(components[k] * weights[k] for k in weights)
    score = _clamp(score)

    return {
        "confidence_score": round(score, 4),
        "components": {k: round(v, 4) for k, v in components.items()},
        "weights": weights,
        "features": {
            k: v for k, v in features.items() if k not in ("mfcc_means", "mfcc_stds")
        },
        "derived": {
            "pitch_cv": round(pitch_cv, 4),
            "range_ratio": round(range_ratio, 4),
            "pause_rep_factor": round(rep_factor, 4),
        },
        "transcript_text": transcript.get("text", ""),
    }


def _print_result(label, result):
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"  CONFIDENCE SCORE: {result['confidence_score']:.4f}")
    print(f"{'=' * 60}")
    print(f"  Components:")
    for name, value in result["components"].items():
        w = result["weights"][name]
        bar = "#" * int(value * 20)
        print(f"    {name:20s}: {value:.4f}  [{bar:<20s}]  (w={w})")
    print(f"  Derived:")
    for name, value in result["derived"].items():
        print(f"    {name:20s}: {value:.4f}")
    print(f"  Key features:")
    for name in (
        "f0_std",
        "f0_mean",
        "f0_range",
        "speech_rate_wpm",
        "pause_count",
        "pause_mean_duration",
        "pause_rate",
        "filler_rate_per_min",
        "hnr",
        "jitter",
        "shimmer",
    ):
        v = result["features"].get(name, "n/a")
        if isinstance(v, float):
            print(f"    {name:25s}: {v:.4f}")
        else:
            print(f"    {name:25s}: {v}")
    print(f"  Transcript: {result['transcript_text'][:120]}...")


if __name__ == "__main__":
    import sys

    files = sys.argv[1:] if len(sys.argv) > 1 else ["test_audio.wav"]

    results = {}
    for audio_path in files:
        print(f"\nAnalyzing: {audio_path} ...")
        results[audio_path] = compute_confidence_score(audio_path)
        _print_result(audio_path, results[audio_path])

    # Summary comparison
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

    with open("confidence_result.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nFull results saved to confidence_result.json")
