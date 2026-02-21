import type { Company } from "./types";

const VIDEO_URL = "https://totsuki.harvey-l.com/0_DjDdfqtUE.mp4";

// Generate confidence data points across ~60 seconds
function generateConfidenceData() {
  const points = [];
  for (let t = 0; t <= 60; t += 2) {
    // Simulate realistic fluctuating confidence with dips
    let confidence = 78 + Math.sin(t * 0.3) * 10 + Math.cos(t * 0.7) * 5;
    // Create deliberate low points
    if (t >= 18 && t <= 22) confidence -= 20;
    if (t >= 42 && t <= 46) confidence -= 25;
    confidence = Math.max(30, Math.min(95, confidence));
    points.push({ timestamp: t, confidence: Math.round(confidence) });
  }
  return points;
}

// Generate bounding box frames (simulating head movement)
function generateBoundingBoxData() {
  const frames = [];
  for (let t = 0; t <= 60; t += 0.5) {
    frames.push({
      timestamp: t,
      x: 35 + Math.sin(t * 0.2) * 3,
      y: 15 + Math.cos(t * 0.15) * 2,
      width: 30,
      height: 38,
    });
  }
  return frames;
}

export const mockCompanies: Company[] = [
  {
    id: "c1",
    name: "TechCorp Inc.",
    people: [
      {
        id: "p1",
        name: "John Doe",
        role: "CEO",
        companyId: "c1",
        videos: [
          {
            id: "v1",
            title: "Q3 2025 Earnings Call",
            date: "2025-09-15",
            videoUrl: VIDEO_URL,
            analysisData: {
              confidenceData: generateConfidenceData(),
              boundingBoxData: generateBoundingBoxData(),
              lowConfidenceMoments: [
                {
                  timestamp: 20,
                  overallConfidence: 58,
                  speechScore: 52,
                  gestureScore: 48,
                  facialScore: 65,
                  statement:
                    "Our revenue projections are... well, optimistic to say the least.",
                  indicators: [
                    "Eye Contact Lost",
                    "Voice Hesitation",
                    "Hand Fidgeting",
                  ],
                },
                {
                  timestamp: 44,
                  overallConfidence: 45,
                  speechScore: 40,
                  gestureScore: 38,
                  facialScore: 55,
                  statement:
                    "The merger timeline is completely on track and we foresee no issues.",
                  indicators: [
                    "Micro-expression: Contempt",
                    "Gaze Aversion",
                    "Speech Rate Increase",
                    "Self-touch Gesture",
                  ],
                },
              ],
            },
          },
          {
            id: "v2",
            title: "Annual Shareholder Meeting",
            date: "2025-06-20",
            videoUrl: VIDEO_URL,
            analysisData: {
              confidenceData: generateConfidenceData(),
              boundingBoxData: generateBoundingBoxData(),
              lowConfidenceMoments: [
                {
                  timestamp: 30,
                  overallConfidence: 62,
                  speechScore: 58,
                  gestureScore: 60,
                  facialScore: 68,
                  statement:
                    "We have no plans to restructure the engineering division.",
                  indicators: ["Lip Compression", "Shoulder Shrug"],
                },
              ],
            },
          },
        ],
      },
      {
        id: "p2",
        name: "Jane Smith",
        role: "CTO",
        companyId: "c1",
        videos: [
          {
            id: "v3",
            title: "Tech Summit Keynote",
            date: "2025-11-10",
            videoUrl: VIDEO_URL,
            analysisData: {
              confidenceData: generateConfidenceData(),
              boundingBoxData: generateBoundingBoxData(),
              lowConfidenceMoments: [
                {
                  timestamp: 35,
                  overallConfidence: 55,
                  speechScore: 50,
                  gestureScore: 45,
                  facialScore: 62,
                  statement:
                    "Our infrastructure can absolutely handle the projected load.",
                  indicators: [
                    "Blink Rate Increase",
                    "Voice Pitch Rise",
                    "Defensive Posture",
                  ],
                },
              ],
            },
          },
        ],
      },
    ],
  },
  {
    id: "c2",
    name: "InnovateLabs",
    people: [
      {
        id: "p3",
        name: "Michael Chen",
        role: "CEO",
        companyId: "c2",
        videos: [
          {
            id: "v4",
            title: "Series C Funding Announcement",
            date: "2025-08-05",
            videoUrl: VIDEO_URL,
            analysisData: {
              confidenceData: generateConfidenceData(),
              boundingBoxData: generateBoundingBoxData(),
              lowConfidenceMoments: [
                {
                  timestamp: 25,
                  overallConfidence: 60,
                  speechScore: 55,
                  gestureScore: 58,
                  facialScore: 66,
                  statement:
                    "We expect to be profitable within the next two quarters.",
                  indicators: [
                    "Eye Contact Lost",
                    "Throat Clearing",
                    "Hand-to-face Gesture",
                  ],
                },
              ],
            },
          },
        ],
      },
      {
        id: "p4",
        name: "Sarah Park",
        role: "CFO",
        companyId: "c2",
        videos: [
          {
            id: "v5",
            title: "Financial Review Q2 2025",
            date: "2025-07-22",
            videoUrl: VIDEO_URL,
            analysisData: {
              confidenceData: generateConfidenceData(),
              boundingBoxData: generateBoundingBoxData(),
              lowConfidenceMoments: [
                {
                  timestamp: 15,
                  overallConfidence: 52,
                  speechScore: 48,
                  gestureScore: 50,
                  facialScore: 58,
                  statement:
                    "Our burn rate is fully sustainable at the current trajectory.",
                  indicators: [
                    "Micro-expression: Fear",
                    "Speech Filler Words",
                    "Postural Shift",
                  ],
                },
              ],
            },
          },
        ],
      },
    ],
  },
  {
    id: "c3",
    name: "Quantum Dynamics",
    people: [
      {
        id: "p5",
        name: "David Wilson",
        role: "CEO",
        companyId: "c3",
        videos: [
          {
            id: "v6",
            title: "Product Launch: QD-7",
            date: "2025-10-01",
            videoUrl: VIDEO_URL,
            analysisData: {
              confidenceData: generateConfidenceData(),
              boundingBoxData: generateBoundingBoxData(),
              lowConfidenceMoments: [
                {
                  timestamp: 40,
                  overallConfidence: 48,
                  speechScore: 42,
                  gestureScore: 44,
                  facialScore: 55,
                  statement:
                    "There are absolutely no safety concerns with the new product line.",
                  indicators: [
                    "Forced Smile",
                    "Rapid Blinking",
                    "Voice Tremor",
                    "Crossed Arms",
                  ],
                },
              ],
            },
          },
        ],
      },
      {
        id: "p6",
        name: "Emily Zhang",
        role: "VP of Engineering",
        companyId: "c3",
        videos: [
          {
            id: "v7",
            title: "Engineering All-Hands",
            date: "2025-09-28",
            videoUrl: VIDEO_URL,
            analysisData: {
              confidenceData: generateConfidenceData(),
              boundingBoxData: generateBoundingBoxData(),
              lowConfidenceMoments: [],
            },
          },
        ],
      },
    ],
  },
];
