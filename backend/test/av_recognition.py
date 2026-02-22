import groq
import cv2
import numpy as np
import os
import subprocess
import json
import tempfile
import uuid
from PIL import Image
from dotenv import load_dotenv
from vector_store import VectorStore
from groq_retry import groq_call_with_retry

load_dotenv()

_groq = groq.Groq(api_key=os.getenv("OPENAI_API_KEY"))
_vector_store = VectorStore(path="./chroma_db")

# Lazy-loaded models
_mtcnn = None
_resnet = None
_voice_enc = None


def _get_face_models():
    global _mtcnn, _resnet
    if _mtcnn is None:
        from facenet_pytorch import MTCNN, InceptionResnetV1

        _mtcnn = MTCNN(keep_all=True)
        _resnet = InceptionResnetV1(pretrained="vggface2").eval()
    return _mtcnn, _resnet


_get_face_models()


def _get_voice_encoder():
    global _voice_enc
    if _voice_enc is None:
        from resemblyzer import VoiceEncoder

        _voice_enc = VoiceEncoder()
    return _voice_enc


_get_voice_encoder()


def _ts_to_sec(ts: str) -> float:
    parts = ts.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(ts)


def _compress_transcript_for_speakers(
    transcript: str, max_lines: int = 400, head_lines: int = 120
) -> str:
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    if len(lines) <= max_lines:
        return transcript

    cue_keywords = (
        "my name is",
        "i'm",
        "i am",
        "introduce",
        "welcome",
        "please welcome",
        "joining me",
        "next speaker",
        "hand over",
        "cto",
        "cfo",
        "ceo",
        "president",
        "vp",
        "svp",
        "chief",
    )

    selected = set(range(min(head_lines, len(lines))))
    selected.update(range(max(0, len(lines) - 40), len(lines)))

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(k in line_lower for k in cue_keywords):
            selected.add(i)
        if i % 5 == 0:
            selected.add(i)

    picked_idx = sorted(selected)[:max_lines]
    return "\n".join(lines[i] for i in picked_idx)


def _grab_frame(video_path: str, sec: float):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
    ok, frame = cap.read()
    cap.release()
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if ok else None


def _embed_single_face(img_array, mtcnn, resnet):
    """Return 512-d embedding ONLY when exactly one face is in the frame."""
    import torch

    pil = Image.fromarray(img_array)
    boxes, probs = mtcnn.detect(pil)
    if boxes is None or len(boxes) != 1:
        return None
    faces = mtcnn(pil)
    if faces is None or len(faces) != 1:
        return None
    with torch.no_grad():
        emb = resnet(faces)
    return emb.squeeze().numpy()


def _robust_face_embedding(video_path, t0, t1, mtcnn, resnet, n_samples=12):
    """Sample many frames, keep only single-face frames, reject outlier embeddings."""
    duration = t1 - t0
    if duration <= 0:
        return None

    step = duration / (n_samples + 1)
    timestamps = [t0 + step * (i + 1) for i in range(n_samples)]

    embeddings = []
    for t in timestamps:
        frame = _grab_frame(video_path, max(t, 0))
        if frame is None:
            continue
        emb = _embed_single_face(frame, mtcnn, resnet)
        if emb is not None:
            embeddings.append(emb)

    if len(embeddings) == 0:
        return None
    if len(embeddings) == 1:
        return embeddings[0].tolist()

    embs = np.array(embeddings)
    # Normalise for cosine similarity
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    normed = embs / np.clip(norms, 1e-9, None)
    sim = normed @ normed.T

    n = len(embs)
    # Average similarity to every *other* embedding
    avg_sim = (sim.sum(axis=1) - 1.0) / max(n - 1, 1)

    # Keep embeddings above (median - 0.5 * std)
    threshold = np.median(avg_sim) - 0.5 * np.std(avg_sim)
    mask = avg_sim >= threshold
    if mask.sum() == 0:
        mask[np.argmax(avg_sim)] = True

    filtered = embs[mask]
    mean_emb = filtered.mean(axis=0)
    mean_emb /= np.linalg.norm(mean_emb)
    n_kept = int(mask.sum())
    n_dropped = n - n_kept
    if n_dropped:
        print(f"    ({n_kept} frames kept, {n_dropped} outliers dropped)")
    return mean_emb.tolist()


def _embed_face_query(img_array, mtcnn, resnet):
    """For find_face queries: embed the largest face in the image."""
    import torch

    pil = Image.fromarray(img_array)
    boxes, _ = mtcnn.detect(pil)
    if boxes is None or len(boxes) == 0:
        return None
    faces = mtcnn(pil)
    if faces is None:
        return None
    # Pick largest face by bounding-box area
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    best = int(np.argmax(areas))
    with torch.no_grad():
        emb = resnet(faces[best].unsqueeze(0))
    return emb.squeeze().numpy().tolist()


def _embed_voice(audio_path: str, encoder):
    from resemblyzer import preprocess_wav

    try:
        wav = preprocess_wav(audio_path)
    except (RuntimeError, OSError, ValueError):
        return None
    if len(wav) < 1600:
        return None
    return encoder.embed_utterance(wav).tolist()


def _web_search(query: str, max_results: int = 5) -> str:
    """Run a web search and return formatted results."""
    from ddgs import DDGS

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    if not results:
        return "(no results)"
    return "\n".join(f"- {r['title']}: {r['body']}" for r in results)


def _lookup_speaker(speaker_id: str) -> dict:
    import requests

    resp = requests.get("http://totsuki.harvey-l.com:7000/people/" + str(speaker_id))
    return resp.json()


def _db_search(query: str, max_results: int = 5) -> str:
    """
    Search in our people database
    """
    import requests

    resp = requests.get(
        "http://totsuki.harvey-l.com:7000/people/search", params={"q": query}
    ).json()
    resp["speakerId"] = resp["id"]
    return json.dumps(resp)


def _db_insert(name: str, organization: str, role: str) -> str:
    import requests

    resp = requests.post(
        "http://totsuki.harvey-l.com:7000/people",
        json={"name": name, "organization": organization, "role": role},
    ).json()
    resp["speakerId"] = resp["id"]
    return json.dumps(resp)


def _execute_tool(name: str, args: dict) -> str:
    if name == "web_search":
        query = args.get("query", "")
        if not str(query).strip():
            return "(missing query)"
        print(f"  Web Searching: {query}")
        return _web_search(query)
    if name == "db_search":
        query = args.get("query", "")
        if not str(query).strip():
            return json.dumps({"error": "missing query"})
        print(f"  DB Searching: {query}")
        return _db_search(query)
    if name == "db_insert":
        payload = {
            "name": args.get("name", ""),
            "organization": args.get("organization", ""),
            "role": args.get("role", ""),
        }
        if not str(payload["name"]).strip():
            return json.dumps({"error": "missing name"})
        print(f"  DB Insert: {payload}")
        return _db_insert(**payload)
    return "(unknown tool)"


def _append_tool_results(messages: list, tool_calls: list) -> None:
    for tc in tool_calls:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        result = _execute_tool(tc.function.name, args)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            }
        )


_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "db_search",
            "description": (
                "Search OUR people database to find the full name, job title, and role of a "
                "person mentioned in a corporate video. Use this for EVERY speaker "
                "to resolve their unique identifier in our DB"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query, e.g. 'Intuit Sasan CEO' or 'Intuit investor day 2025 speakers'",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "db_insert",
            "description": (
                "Insert the full name, organization, and role of a speaker to the database. Returns a unique identifier."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Full name of the people. e.g. 'Elon Musk'",
                    },
                    "organization": {
                        "type": "string",
                        "description": "The company this person belongs to. e.g. 'Google'",
                    },
                    "role": {
                        "type": "string",
                        "description": "The role of this person in the company. Can be empty. e.g. 'CTO'",
                    },
                },
                "required": [],
            },
        },
    },
]

_SYSTEM_PROMPT = """\
You are an expert at analyzing corporate video transcripts (investor days, \
earnings calls, product launches, keynotes) to identify every speaker.

Your task:
1. Read the transcript carefully. Identify the company and event type.
2. Extract every person mentioned or implied as a speaker: look for \
   introductions ("please welcome..."), name drops ("after Sasan, Alex will..."), \
   self-introductions, and speaker transitions.
3. For EACH speaker, use db_search to check if it is already in our database.
4. If a speaker is missing, infer best-effort name/title from transcript context and insert with db_insert.
5. Return only the segments that you are certain is said by the speaker. As many as possible, but don't have to be exaustive. \
   Ignore ambiguous sentences like "Thank you".
6. Ensure all the people are either already existing in the db, or inserted with db_insert.
"""


def index_face_audio(av_path: str, transcript: str, desc: str, is_audio: bool = False):
    """
    av_path: any video / wav file
    Step 1: Use transcript and LLM (DB tools only) to associate
            speaker full names with their appearance times in the video.
    Step 2: Extract face and audio keypoints and add them to a vector database.
    """
    _vector_store.reset_face_audio_collections()

    # ── Get duration ──────────────────────────────────────────
    duration = 0.0
    res = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            av_path,
        ],
        capture_output=True,
        text=True,
    )
    try:
        duration = float(res.stdout.strip())
    except:
        duration = 0.0

    transcript_for_speakers = _compress_transcript_for_speakers(transcript)

    # ── Phase 1: tool-use loop — research speakers ────────────
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Video description: {desc}
Video duration: {duration:.0f} seconds ({duration / 60:.1f} minutes)

Condensed transcript (speaker-focused):
{transcript_for_speakers}

Identify every speaker with their full name and title. Ensure that they are in our database, then return the segments linked with speakerId.""",
        },
    ]

    print("Identifying speakers (with web search)...")
    for i in range(100):
        resp = groq_call_with_retry(
            lambda: _groq.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=messages,
                tools=_TOOLS,
                temperature=0,
            ),
            op_name=f"av_recognition.step1.turn_{i}",
        )

        msg = resp.choices[0].message

        if msg.tool_calls:
            messages.append(msg)
            _append_tool_results(messages, msg.tool_calls)

        else:
            # Model finished researching — append its summary
            messages.append(msg)
            break

    # ── Phase 2: structured output — continue the same conversation ────────
    messages.append(
        {
            "role": "user",
            "content": (
                "Now output ONLY a JSON object with key 'segments' containing an array. "
                "Each element must have: speakerId (from our DB), start (M:SS), end (M:SS). "
                "Merge consecutive segments for the same speaker. Order by appearance time."
            ),
        }
    )
    data = {"segments": []}
    for i in range(20):
        structured_resp = groq_call_with_retry(
            lambda: _groq.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=messages,
                tools=_TOOLS,
                temperature=0,
            ),
            op_name=f"av_recognition.step2.turn_{i}",
        )
        structured_msg = structured_resp.choices[0].message
        if structured_msg.tool_calls:
            messages.append(structured_msg)
            _append_tool_results(messages, structured_msg.tool_calls)
            continue
        messages.append(structured_msg)
        raw_content = structured_msg.content or "{}"
        try:
            data = json.loads(raw_content)
            break
        except json.JSONDecodeError:
            start = raw_content.find("{")
            end = raw_content.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    data = json.loads(raw_content[start : end + 1])
                    break
                except json.JSONDecodeError:
                    pass
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Return only valid JSON with key 'segments'. No markdown, no prose."
                    ),
                }
            )

    speakers = data.get("segments", [])

    print(f"\nIdentified {len(speakers)} speaker segment(s):")
    for s in speakers:
        print(f"  {s}")

    # ── Extract face + audio embeddings ───────────────────────
    mtcnn, resnet = (None, None) if is_audio else _get_face_models()
    voice_enc = _get_voice_encoder()
    run_id = uuid.uuid4().hex[:8]

    for i, sp in enumerate(speakers):
        speaker_id = sp["speakerId"]
        t0 = _ts_to_sec(sp["start"])
        t1 = _ts_to_sec(sp["end"])
        meta = {"speakerId": speaker_id, "start": t0, "end": t1}
        info = _lookup_speaker(speaker_id)
        display_name = info.get("name", speaker_id)

        # Face: multi-frame sampling with outlier rejection
        # Save some CPU. Disable this
        # if not is_audio:
        #     emb = _robust_face_embedding(av_path, t0, t1, mtcnn, resnet)
        #     if emb:
        #         _vector_store.add_face_embedding(f"face_{run_id}_{i}", emb, meta)
        #         print(f"  + face  {display_name}")
        #     else:
        #         print(f"  - face  {display_name}  (no single-face frame found)")
        # else:
        #     print(f"  . face  {display_name}  (skipped in audio-only mode)")

        # Audio: extract segment and embed voice
        segment_duration = max(0.0, t1 - t0)
        if segment_duration < 0.2:
            print(f"  - audio {display_name}  (segment too short)")
            continue
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        ffmpeg_res = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(max(0.0, t0)),
                "-t",
                str(segment_duration),
                "-i",
                av_path,
                "-vn",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-acodec",
                "pcm_s16le",
                wav_path,
            ],
            capture_output=True,
            text=True,
        )
        try:
            if ffmpeg_res.returncode != 0:
                print(f"  - audio {display_name}  (ffmpeg failed)")
                continue
            if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1024:
                print(f"  - audio {display_name}  (invalid wav segment)")
                continue
            emb = _embed_voice(wav_path, voice_enc)
            if emb:
                _vector_store.add_audio_embedding(f"audio_{run_id}_{i}", emb, meta)
                print(f"  + audio {display_name}")
            else:
                print(f"  - audio {display_name}  (no voice embedding)")
        except (RuntimeError, ValueError, OSError) as e:
            print(f"  - audio {display_name}  (embed error: {e})")
        finally:
            if os.path.exists(wav_path):
                os.unlink(wav_path)

    print("Indexing complete.")
    return speakers


def find_face(image_path: str):
    """Lookup in the database for a face."""
    mtcnn, resnet = _get_face_models()

    img = np.array(Image.open(image_path).convert("RGB"))
    emb = _embed_face_query(img, mtcnn, resnet)
    if emb is None:
        return [{"error": "No face detected"}]

    res = _vector_store.query_face_embeddings(emb, n_results=3)
    return [
        {
            "speakerId": m.get("speakerId", ""),
            **_lookup_speaker(m.get("speakerId", "")),
            "distance": d,
            "start": m.get("start"),
            "end": m.get("end"),
            "time": f"{m.get('start', 0):.0f}s-{m.get('end', 0):.0f}s",
        }
        for m, d in zip(res["metadatas"][0], res["distances"][0])
    ]


def find_audio(audio_path: str):
    """Lookup for the audio."""
    enc = _get_voice_encoder()

    emb = _embed_voice(audio_path, enc)
    if emb is None:
        return [{"error": "Could not process audio"}]

    res = _vector_store.query_audio_embeddings(emb, n_results=3)
    return [
        {
            "speakerId": m.get("speakerId", ""),
            **_lookup_speaker(m.get("speakerId", "")),
            "distance": d,
            "start": m.get("start"),
            "end": m.get("end"),
            "time": f"{m.get('start', 0):.0f}s-{m.get('end', 0):.0f}s",
        }
        for m, d in zip(res["metadatas"][0], res["distances"][0])
    ]
