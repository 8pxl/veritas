import os
from pyannote.audio import Pipeline
import torch
from dotenv import load_dotenv

# Ensure pydub (and underlying ffmpeg/avlib) is installed for mp3->wav conversion.
# You can install it via: pip install pydub

load_dotenv()


def convert_mp3_to_wav(input_path):
    """Convert an MP3 file to WAV and return the path to the wav file.
    The WAV file is written to the same directory with the same base name.
    """
    from pydub import AudioSegment

    base, ext = os.path.splitext(input_path)
    if ext.lower() != ".mp3":
        # nothing to do
        return input_path

    wav_path = base + ".wav"
    # only convert if wav does not already exist
    if not os.path.exists(wav_path):
        audio = AudioSegment.from_mp3(input_path)
        audio.export(wav_path, format="wav")
    return wav_path


def get_speaker_segments(audio_path, hf_token):
    # ensure we have a WAV file for the diarization pipeline
    audio_path = convert_mp3_to_wav(audio_path)

    # 1. Load the pipeline
    # Use 'cuda' if you have a GPU, otherwise 'cpu'
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=hf_token
    )
    
    if torch.cuda.is_available():
        pipeline.to(torch.device("mps"))

    # 2. Run diarization
    print("Analyzing speakers...")
    diarization = pipeline(audio_path)

    # 3. Process the output
    speaker_map = []
    for turn, speaker in diarization.exclusive_speaker_diarization:
        segment = {
            "start": round(turn.start, 2),
            "end": round(turn.end, 2),
            "speaker": speaker
        }
        speaker_map.append(segment)
        print(f"[{segment['start']}s - {segment['end']}s] {speaker}")
    
    return speaker_map

# Usage
segments = get_speaker_segments("temp_audio.mp3", os.getenv("HF_KEY"))
print(segments)