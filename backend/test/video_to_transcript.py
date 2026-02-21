'''
This module contains functions to convert a video file to a transcript with speaker annotations. It uses the pyannote.audio library for speaker diarization and the OpenAI Whisper API for transcription.
'''
from annotation import get_speaker_segments
from transcribe import transcribe_with_groq


def assign_speakers_to_word(whisper_words, speaker_segments):
    """Merge Whisper word segments with speaker labels and return list of dicts.

    Each output element contains:
      start, end, speaker, text
    """
    final_transcript = []

    for ws in whisper_words:
        # Find the speaker active during the midpoint of this text segment
        midpoint = (ws.start + ws.end) / 2

        # Simple match: find speaker whose [start, end] contains the midpoint
        current_speaker = "Unknown"
        for ss in speaker_segments:
            if ss['start'] <= midpoint <= ss['end']:
                current_speaker = ss['speaker']
                break

        final_transcript.append({
            "start": round(ws.start, 2),
            "end": round(ws.end, 2),
            "speaker": current_speaker,
            "text": ws.word
        })

    return final_transcript

def assign_speakers_to_text(whisper_segments, speaker_segments):
    """Merge Whisper segments with speaker labels and return list of dicts.

    Each output element contains:
      start, end, speaker, text
    """
    final_transcript = []

    for ws in whisper_segments:
        # Find the speaker active during the midpoint of this text segment
        midpoint = (ws.start + ws.end) / 2

        # Simple match: find speaker whose [start, end] contains the midpoint
        current_speaker = "Unknown"
        for ss in speaker_segments:
            if ss['start'] <= midpoint <= ss['end']:
                current_speaker = ss['speaker']
                break

        final_transcript.append({
            "start": round(ws.start, 2),
            "end": round(ws.end, 2),
            "speaker": current_speaker,
            "text": ws.text
        })

    return final_transcript

# Example usage
if __name__ == "__main__":
    # Step 1: Get speaker segments from the audio file
    speaker_segments = get_speaker_segments("temp_audio.mp3", hf_token="your_hf_token_here")
    
    # Step 2: Get transcription segments from the audio file
    whisper_words, whisper_segments = transcribe_with_groq("temp_audio.mp3")
    final_transcript_words = assign_speakers_to_word(whisper_words, speaker_segments)
    # Step 3: Combine them into a final transcript with speaker labels
    final_transcript = assign_speakers_to_text(whisper_segments, speaker_segments)
    
    # Print the final transcript as JSON
    import json
    json_output = json.dumps(final_transcript, indent=2)
    print(json_output)

    # Optionally save to a file
    out_path = "transcript.json"
    with open(out_path, "w") as f:
        f.write(json_output)
    print(f"Saved JSON transcript to {out_path}")
    
    # Save the words transcript to json also
    words_path = "transcript_words.json"
    words_json = json.dumps(final_transcript_words, indent=2)
    with open(words_path, "w") as f:
        f.write(words_json)
    print(f"Saved JSON words transcript to {words_path}")


##
'''
Output: JSON output with each element containing:
- start: start time of the segment
- end: end time of the segment
- speaker: speaker label (e.g., "Speaker 1", "Speaker 2", etc.)
- text: transcribed text for that segment

'''