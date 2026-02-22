"use client"

import { useEffect, useState, useRef } from "react"
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

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 70 ? "bg-green-400" : pct >= 40 ? "bg-yellow-400" : "bg-red-400"
  return (
    <div className="flex items-center gap-2">
      <span className="w-28 shrink-0 text-[10px] text-white/50 truncate capitalize">{label.replace(/_/g, " ")}</span>
      <div className="flex-1 h-1 rounded-full bg-white/10">
        <div className={`h-1 rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-6 text-right text-[10px] text-white/50">{pct}</span>
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
      <Card className="border-white/10 bg-black/70 text-white backdrop-blur-xl shadow-2xl py-4 gap-3">
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
              <div className="h-1.5 w-full rounded-full bg-white/10">
                <div
                  className={`h-1.5 rounded-full transition-all ${audio.confidence_score >= 0.7 ? "bg-green-400" : audio.confidence_score >= 0.4 ? "bg-yellow-400" : "bg-red-400"}`}
                  style={{ width: `${Math.round(audio.confidence_score * 100)}%` }}
                />
              </div>
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
              <div className="h-1.5 w-full rounded-full bg-white/10">
                <div
                  className={`h-1.5 rounded-full transition-all ${facial.confidence_score >= 0.7 ? "bg-green-400" : facial.confidence_score >= 0.4 ? "bg-yellow-400" : "bg-red-400"}`}
                  style={{ width: `${Math.round(facial.confidence_score * 100)}%` }}
                />
              </div>
              {facial.components && (
                <div className="flex flex-col gap-1 pt-0.5">
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

