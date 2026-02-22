import { useState, useEffect, useMemo, RefObject } from "react"
import { PropositionsWithAnalysis } from "../stores/useExploreStore"
import { ScoreBar, emotionColor, buildWaveformPath, W, H } from "./ConfidencePopup"
import { AudioWaveform } from "lucide-react"
import F0Vis from "./F0Vis"
export function AudioEmotionOverlay({
  proposition,
  visible,
  videoRef,
}: {
  proposition: PropositionsWithAnalysis
  visible: boolean
  videoRef: RefObject<HTMLVideoElement>
}) {
  const [animState, setAnimState] = useState<"entering" | "visible" | "exiting" | "hidden">("hidden")

  useEffect(() => {
    if (visible) {
      setAnimState("entering")
      const frame = requestAnimationFrame(() => setTimeout(() => setAnimState("visible"), 16) as unknown as void)
      return () => cancelAnimationFrame(frame as unknown as number)
    } else {
      setAnimState("exiting")
      const timer = setTimeout(() => setAnimState("hidden"), 500)
      return () => clearTimeout(timer)
    }
  }, [visible])

  const audio = proposition.audio_confidence
  const facial = proposition.facial_confidence
  const hasFacial = facial && !facial.error

  const wavePath = useMemo(() => buildWaveformPath(
    proposition.id,
    audio?.features?.f0_std ?? 30,
    audio?.features?.f0_range ?? 100,
  ), [audio, proposition.id])

  const topEmotions = useMemo(() => {
    if (!hasFacial) return []
    const emotions = facial.features?.emotions ?? {}
    const dominantCounts = facial.features?.dominant_emotion_counts ?? {}
    // Prefer dominant_emotion_counts if available, else fall back to emotions.mean
    const entries =
      Object.keys(dominantCounts).length > 0
        ? Object.entries(dominantCounts).map(([name, count]) => ({
          name,
          value: count as number,
        }))
        : Object.entries(emotions).map(([name, val]) => ({
          name,
          value: val.mean,
        }))
    const total = entries.reduce((s, e) => s + e.value, 0) || 1
    return entries
      .map((e) => ({ ...e, pct: e.value / total }))
      .filter((e) => e.pct > 0.01)
      .sort((a, b) => b.pct - a.pct)
      .slice(0, 5)
  }, [facial, hasFacial])

  if (animState === "hidden") return null
  const show = animState === "visible"

  const audioScore = audio ? Math.round(audio.confidence_score * 100) : null

  return (
    <div
      className={`absolute left-4 top-4 z-20 w-44 transition-all duration-500 ease-in-out ${show ? "translate-y-0 opacity-100" : "-translate-y-3 opacity-0 pointer-events-none"
        }`}
    >
      <div className="rounded-xl border border-white/10 bg-black/25 backdrop-blur-sm shadow-2xl p-3 flex flex-col gap-3">
        <div className="text-sm text-white">
          F0 Vis:
        </div>

        <F0Vis
          mean={audio?.features?.f0_std ?? 30}
          stdev={audio?.features?.f0_range ?? 100}
          videoRef={videoRef}
        />


        {/* Emotions */}
        {topEmotions.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <span className="text-[9px] uppercase tracking-widest text-white/30 font-medium">Affect</span>
            {topEmotions.map(({ name, pct }) => (
              <ScoreBar
                key={name}
                label={name}
                value={pct}
                barColor={emotionColor(name)}
                height="h-[3px]"
                labelWidth="w-14"
                labelColor={emotionColor(name)}
                labelSize="text-[10px]"
                valueSize="text-[9px]"
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
