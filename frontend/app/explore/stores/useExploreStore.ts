import { create } from "zustand";
import type { Video, Proposition, Person } from "@/lib/client/types.gen";

export interface AudioConfidence {
    confidence_score: number;
    error?: string;
    components?: {
        pitch_stability: number;
        speech_rate: number;
        pause_fluency: number;
        filler_control: number;
        voice_quality: number;
    };
    weights?: {
        pitch_stability: number;
        speech_rate: number;
        pause_fluency: number;
        filler_control: number;
        voice_quality: number;
    };
    features: {
        f0_mean: number;
        f0_std: number;
        f0_range: number;
        f0_median: number;
        voiced_fraction: number;
        jitter: number;
        shimmer: number;
        hnr: number;
        energy_mean: number;
        energy_std: number;
        energy_range: number;
        speech_rate_wpm: number;
        pause_count: number;
        pause_mean_duration: number;
        pause_rate: number;
        filler_rate_per_min: number;
        articulation_ratio: number;
    };
    derived: {
        pitch_cv: number
        range_ratio: number;
        pause_rep_factor: number;
    };
    transcript_text: string;
}

export interface FacialConfidence {
    confidence_score: number;
    components: {
        composure: number;
        positive_affect: number;
        emotional_stability: number;
        gaze_stability: number;
        neutrality: number;
    };
    weights: {
        composure: number;
        positive_affect: number;
        emotional_stability: number;
        gaze_stability: number;
        neutrality: number;
    };
    features: {
        frames_extracted: number;
        analysis_frames_extracted: number;
        analysis_frames_selected: number;
        bbox_fps: number;
        analysis_fps: number;
        face_score_threshold: number;
        frames_with_faces: number;
        no_face_frames: number;
        faces_detected: number;
        timing: {
            bbox_detection_s: number;
            frame_extraction_s: number;
            detection_s: number;
            total_s: number;
        };
        au: Record<string, { mean: number; std: number; max: number }>;
        emotions: Record<string, { mean: number; std: number }>;
        pose: Record<string, { mean: number; std: number }>;
        dominant_emotion_counts: Record<string, number>;
    };
}

export interface PropositionsWithAnalysis extends Proposition {
  audio_confidence: AudioConfidence;
  facial_confidence: FacialConfidence & { error?: string };
  start: string; 
  end: string;
}

interface ExploreState {
  selectedVideo: Video | null;
  selectedPerson: Person | null;
  selectedOrgName: string | null;
  propositions: PropositionsWithAnalysis[];
  selectVideo: (video: Video, person: Person, orgName: string, propositions: PropositionsWithAnalysis[]) => void;
  clearSelection: () => void;
}

export const useExploreStore = create<ExploreState>((set) => ({
  selectedVideo: null,
  selectedPerson: null,
  selectedOrgName: null,
  propositions: [],
  selectVideo: (video, person, orgName, propositions) =>
    set({ selectedVideo: video, selectedPerson: person, selectedOrgName: orgName, propositions }),
  clearSelection: () =>
    set({ selectedVideo: null, selectedPerson: null, selectedOrgName: null, propositions: [] }),
}));
