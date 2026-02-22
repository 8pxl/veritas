"use client"

import { useEffect, useState, useRef, useMemo } from "react"
import { CheckCircle, XCircle, Mic, Eye, AlertTriangle } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PropositionsWithAnalysis } from "../stores/useExploreStore"

function Typewriter({ text, speed = 25 }: { text: string; speed?: number }) {
  const [displayed, setDisplayed] = useState("")
  const indexRef = useRef(0)

  useEffect(() => {
    setDisplayed("")
    indexRef.current = 0

    const interval = setInterval(() => {
      indexRef.current++
      if (indexRef.current <= text.length) {
        setDisplayed(text.slice(0, indexRef.current))
      } else {
        clearInterval(interval)
      }
    }, speed)

    return () => clearInterval(interval)
  }, [text, speed])

  return (
    <>
      {displayed}
      {displayed.length < text.length && (
        <span className="inline-block w-px h-3 bg-white/60 animate-pulse ml-px align-baseline" />
      )}
    </>
  )
}

interface ScoreBarProps {
  /** Optional label shown to the left of the bar */
  label?: string
  /** 0-1 score value */
  value: number
  /** Override bar color (hex). When omitted, auto-picks green/yellow/red. */
  barColor?: string
  /** Tailwind height class for the bar track + fill, e.g. "h-1.5" (default "h-0.75") */
  height?: string
  /** Tailwind width class for the label, e.g. "w-14" (default "w-28") */
  labelWidth?: string
  /** Label color as hex string for inline style. Falls back to white/50 when omitted. */
  labelColor?: string
  /** Font-size class for label (default "text-[10px]") */
  labelSize?: string
  /** Font-size class for the percentage number (default "text-[10px]") */
  valueSize?: string
  /** Whether to show the numeric percentage (default true) */
  showValue?: boolean
}

export function ScoreBar({
  label,
  value,
  barColor,
  height = "h-0.75",
  labelWidth = "w-28",
  labelColor,
  labelSize = "text-[10px]",
  valueSize = "text-[10px]",
  showValue = true,
}: ScoreBarProps) {
  const pct = Math.round(value * 100)

  // Derive colour — explicit hex wins, otherwise threshold-based class
  const autoHex = pct >= 70 ? "#4ade80" : pct >= 40 ? "#facc15" : "#f87171"
  const hex = barColor ?? autoHex
  const autoClass = pct >= 70 ? "bg-green-400" : pct >= 40 ? "bg-yellow-400" : "bg-red-400"

  return (
    <div className="flex items-center gap-2 transition-all">
      {label !== undefined && (
        <span
          className={`${labelWidth} shrink-0 ${labelSize} truncate capitalize ${labelColor ? "" : "text-white/50"}`}
          style={labelColor ? { color: labelColor } : undefined}
        >
          {label.replace(/_/g, " ")}
        </span>
      )}
      <div className={`flex-1 ${height} rounded-full bg-white/10`}>
        <div
          className={`${height} rounded-full transition-all duration-1000 ${barColor ? "" : autoClass}`}
          style={{
            width: `${pct}%`,
            ...(barColor ? { backgroundColor: hex } : {}),
            boxShadow: `0 0 4px 1px ${hex}90`,
          }}
        />
      </div>
      {showValue && (
        <span className={`w-6 text-right ${valueSize} text-white/50 shrink-0`}>{pct}</span>
      )}
    </div>
  )
}

interface PropositionPopupProps {
  proposition: PropositionsWithAnalysis
  visible: boolean
  onDismiss: () => void
}

export function PropositionPopup({ proposition, visible, onDismiss }: PropositionPopupProps) {
  const [animState, setAnimState] = useState<"entering" | "visible" | "exiting" | "hidden">("hidden")

  useEffect(() => {
    if (visible) {
      setAnimState("entering")
      const frame = requestAnimationFrame(() => {
        setAnimState("visible")
      })
      return () => cancelAnimationFrame(frame)
    } else {
      setAnimState("exiting")
      const timer = setTimeout(() => {
        setAnimState("hidden")
      }, 500)
      return () => clearTimeout(timer)
    }
  }, [visible])

  if (animState === "hidden") return null

  const show = animState === "visible"

  const audio = proposition.audio_confidence
  const facial = proposition.facial_confidence
  const hasFacial = facial && !facial.error

  const verdict = proposition.verdict?.toLowerCase()
  const verdictColor =
    verdict === "true" ? "text-green-400" :
      verdict === "false" ? "text-red-400" :
        "text-yellow-400"
  const VerdictIcon =
    verdict === "true" ? CheckCircle :
      verdict === "false" ? XCircle :
        AlertTriangle

  return (
    <div className={`absolute right-4 top-4 z-20 w-80 transition-all duration-500 ease-in-out ${show ? "translate-y-0 opacity-100" : "-translate-y-4 opacity-0 pointer-events-none"}`}>
      <Card className="border-white/10 bg-black/25 text-white backdrop-blur-sm shadow-2xl py-4 gap-3">
        <CardHeader className="pb-0">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="size-4 text-yellow-400" />
              <CardTitle className="text-sm">Verify Claim</CardTitle>
            </div>
            <button onClick={onDismiss} className="text-white/40 hover:text-white/80 transition-colors text-xs leading-none">
              &#x2715;
            </button>
          </div>
        </CardHeader>

        <CardContent className="flex flex-col gap-3">
          {/* Speaker info */}
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-semibold">{proposition.speaker?.name ?? "Unknown Speaker"}</span>
            {proposition.speaker?.position ? (
              <span className="text-xs text-white/50">{proposition.speaker.position}</span>
            ) : (
              <span className="text-xs text-white/30 italic">No position available</span>
            )}
          </div>

          {/* Statement with typewriter */}
          <p className="text-xs italic text-white/70 leading-relaxed border-l-2 border-white/20 pl-2 min-h-[2.5em]">
            &ldquo;<Typewriter text={proposition.statement} />&rdquo;
          </p>

          {/* Verdict */}
          {verdict && (
            <div className="flex flex-col gap-1 rounded-md bg-white/5 px-3 py-2">
              <div className={`flex items-center gap-1.5 text-xs font-semibold ${verdictColor}`}>
                <VerdictIcon className="size-3.5" />
                {verdict === "true" ? "Likely True" : verdict === "false" ? "Likely False" : "Uncertain"}
              </div>
              {proposition.verdictReasoning && (
                <p className="text-[10px] text-white/50 leading-relaxed">{proposition.verdictReasoning}</p>
              )}
            </div>
          )}

          {/* Audio confidence */}
          {audio && (
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-1.5">
                <Mic className="size-3 text-white/40" />
                <span className="text-[10px] uppercase tracking-wide text-white/40 font-medium">Audio Confidence</span>
                <span className="ml-auto text-xs font-semibold text-white/80">{Math.round(audio.confidence_score * 100)}%</span>
              </div>
              <ScoreBar value={audio.confidence_score} height="h-1.5" showValue={false} />
              {audio.components && (
                <div className="flex flex-col gap-1 pt-0.5">
                  {Object.entries(audio.components).map(([k, v]) => (
                    <ScoreBar key={k} label={k} value={v as number} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Facial confidence */}
          {hasFacial && (
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-1.5">
                <Eye className="size-3 text-white/40" />
                <span className="text-[10px] uppercase tracking-wide text-white/40 font-medium">Facial Confidence</span>
                <span className="ml-auto text-xs font-semibold text-white/80">{Math.round(facial.confidence_score * 100)}%</span>
              </div>
              <ScoreBar value={facial.confidence_score} height="h-1.5" showValue={false} />
              {facial.components && (
                <div className="flex flex-col gap-1 pt-0.5 ">
                  {Object.entries(facial.components).map(([k, v]) => (
                    <ScoreBar key={k} label={k} value={v as number} />
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ─── Left-side audio / emotion overlay ───────────────────────────────────────

const EMOTION_COLORS: Record<string, string> = {
  happy: "#fbbf24",
  joy: "#fbbf24",
  neutral: "#94a3b8",
  sad: "#60a5fa",
  sadness: "#60a5fa",
  angry: "#f87171",
  anger: "#f87171",
  fear: "#c084fc",
  disgust: "#4ade80",
  surprise: "#fb923c",
}

export function emotionColor(name: string) {
  return EMOTION_COLORS[name.toLowerCase()] ?? "#e2e8f0"
}

export const W = 160
export const H = 44

/** Build an SVG path string for a pseudo-waveform */
export function buildWaveformPath(propId: number, f0Std: number, f0Range: number): string {
  const seed = propId * 9301 + 49297
  const amp = Math.max(Math.min(f0Std / Math.max(f0Range, 1), 0.42), 0.12)
  const ph1 = ((seed * 31) % 1000) / 1000 * Math.PI * 2
  const ph2 = ((seed * 53) % 1000) / 1000 * Math.PI * 2
  const n = 48
  const pts = Array.from({ length: n }, (_, i) => {
    const t = i / (n - 1)
    const y = 0.5
      + amp * 0.55 * Math.sin(t * Math.PI * 4 + ph1)
      + amp * 0.28 * Math.sin(t * Math.PI * 9 + ph2)
      + amp * 0.17 * Math.sin(t * Math.PI * 17)
    return [t * W, H - Math.max(0.05, Math.min(0.95, y)) * H] as [number, number]
  })
  let d = `M ${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1]
    const [x1, y1] = pts[i]
    const cx = (x0 + x1) / 2
    d += ` C ${cx.toFixed(1)},${y0.toFixed(1)} ${cx.toFixed(1)},${y1.toFixed(1)} ${x1.toFixed(1)},${y1.toFixed(1)}`
  }
  // close area back to baseline
  d += ` L ${W},${H} L 0,${H} Z`
  return d
}


export function AudioEmotionOverlay({
  proposition,
  visible,
}: {
  proposition: PropositionsWithAnalysis
  visible: boolean
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
      <div className="rounded-xl border border-white/10 bg-black/75 backdrop-blur-xl shadow-2xl p-3 flex flex-col gap-3">
        {/* Pitch waveform — plain SVG, always visible */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="text-[9px] uppercase tracking-widest text-white/30 font-medium">Pitch</span>
            {audioScore !== null && (
              <span className="text-[9px] text-white/40">{audioScore}%</span>
            )}
          </div>
          <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="w-full overflow-visible">
            <defs>
              <linearGradient id="wfGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f472b6" stopOpacity={0.55} />
                <stop offset="100%" stopColor="#894048" stopOpacity={0.03} />
              </linearGradient>
            </defs>
            {/* filled area */}
            <path d={wavePath} fill="url(#wfGrad)" />
            {/* stroke only — same path minus the close */}
            <path
              d={wavePath.split(" L ")[0]}
              fill="none"
              stroke="#f472b6"
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>

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
