export interface ConfidencePoint {
  timestamp: number;
  confidence: number;
}

export interface BoundingBoxFrame {
  timestamp: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface LowConfidenceMoment {
  timestamp: number;
  overallConfidence: number;
  speechScore: number;
  gestureScore: number;
  facialScore: number;
  statement: string;
  indicators: string[];
}

export interface AnalysisData {
  confidenceData: ConfidencePoint[];
  boundingBoxData: BoundingBoxFrame[];
  lowConfidenceMoments: LowConfidenceMoment[];
}

export interface Video {
  id: string;
  title: string;
  date: string;
  videoUrl: string;
  analysisData: AnalysisData;
}

export interface Person {
  id: string;
  name: string;
  role: string;
  companyId: string;
  videos: Video[];
}

export interface Company {
  id: string;
  name: string;
  people: Person[];
}
