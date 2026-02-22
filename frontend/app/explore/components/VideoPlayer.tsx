"use client"

import { useRef, useState, useCallback, useEffect } from "react"
import { PropositionsWithAnalysis, useExploreStore } from "../stores/useExploreStore"
import { PropositionPopup } from "./ConfidencePopup"
import { SkipForward } from "lucide-react"
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid,
} from "recharts"

const TRIGGER_WINDOW = 1.5 // seconds — how close to a timestamp before triggering
const DISMISS_AFTER = 8 // seconds — auto-dismiss if not manually closed

function parseTimestamp(verifyAt: string): number {
  // Try raw number first
  const num = Number(verifyAt)
  if (!isNaN(num)) return num

  // Try MM:SS or HH:MM:SS
  const parts = verifyAt.split(":").map(Number)
  if (parts.length === 2) return parts[0] * 60 + parts[1]
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2]

  return 0
}


export function VideoPlayer() {
  const { selectedVideo, selectedPerson, selectedOrgName, propositions } = useExploreStore()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [activeProposition, setActiveProposition] = useState<PropositionsWithAnalysis | null>(null)
  const [popupVisible, setPopupVisible] = useState(false)
  const triggeredRef = useRef<Set<number>>(new Set())
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Reset triggered set when video changes
  useEffect(() => {
    triggeredRef.current.clear()
    setActiveProposition(null)
    setPopupVisible(false)
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
  }, [selectedVideo?.video_id])

  const handleTimeUpdate = useCallback(() => {
    if (!videoRef.current || !selectedVideo || propositions.length === 0) return
    const currentTime = videoRef.current.currentTime

    for (const prop of propositions) {
      const ts = parseTimestamp(prop.start)
      const end = parseTimestamp(prop.end)
      if (triggeredRef.current.has(prop.id)) continue

      if (currentTime >= ts && currentTime <= end) {
        console.log(prop)
        triggeredRef.current.add(prop.id)
        console.log(`Triggering proposition ${prop} at time ${currentTime}s (timestamp: ${ts}s - ${end}s)`)
        setActiveProposition(prop)
        setPopupVisible(true)

        // Clear any existing dismiss timer
        if (dismissTimerRef.current) {
          clearTimeout(dismissTimerRef.current)
        }
        dismissTimerRef.current = setTimeout(() => {
          setPopupVisible(false)
        }, DISMISS_AFTER * 1000)

        break
      }
    }
  }, [selectedVideo, propositions])

  // Allow re-triggering when user seeks backward past a proposition
  const handleSeeked = useCallback(() => {
    if (!videoRef.current || propositions.length === 0) return
    const currentTime = videoRef.current.currentTime

    for (const prop of propositions) {
      const ts = parseTimestamp(prop.start)
      if (currentTime < ts) {
        triggeredRef.current.delete(prop.id)
      }
    }
  }, [propositions])

  const handleDismiss = useCallback(() => {
    setPopupVisible(false)
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
  }, [])

  const jumpToProposition = useCallback((prop: PropositionsWithAnalysis) => {
    if (!videoRef.current) return
    const ts = parseTimestamp(prop.start)
    // Clear triggered state so the popup can fire again
    triggeredRef.current.delete(prop.id)
    videoRef.current.currentTime = ts
    videoRef.current.play()
    // Show popup immediately
    setActiveProposition(prop)
    setPopupVisible(true)
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
    dismissTimerRef.current = setTimeout(() => setPopupVisible(false), DISMISS_AFTER * 1000)
  }, [])

  const jumpToNextStatement = useCallback(() => {
    if (!videoRef.current || propositions.length === 0) return
    const currentTime = videoRef.current.currentTime
    const sorted = [...propositions].sort((a, b) => parseTimestamp(a.start) - parseTimestamp(b.start))
    const next = sorted.find((p) => parseTimestamp(p.start) > currentTime + 0.5)
    if (next) {
      videoRef.current.currentTime = parseTimestamp(next.start)
      videoRef.current.play()
    }
  }, [propositions])

  const sortedPropositions = [...propositions].sort(
    (a, b) => parseTimestamp(a.start) - parseTimestamp(b.start)
  )

  // Build smoothed chart data from sorted propositions
  const chartData = sortedPropositions.map((prop) => {
    const ts = parseTimestamp(prop.start)
    const m = Math.floor(ts / 60)
    const s = Math.floor(ts % 60)
    const label = `${m}:${String(s).padStart(2, "0")}`
    return {
      label,
      audio: prop.audio_confidence?.confidence_score != null
        ? Math.round(prop.audio_confidence.confidence_score * 100)
        : null,
      facial: prop.facial_confidence && !prop.facial_confidence.error
        ? Math.round(prop.facial_confidence.confidence_score * 100)
        : null,
    }
  })

  if (!selectedVideo) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <p>Select a video from the sidebar to begin analysis.</p>
      </div>
    )
  }



  return (
    <div className="flex flex-1 flex-col gap-4">
      {/* Title row */}
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-semibold">{selectedVideo.title}</h2>
        <p className="text-sm text-muted-foreground">
          {selectedPerson?.name ?? ""} &middot; {selectedOrgName ?? ""} &middot; {selectedVideo.time}
        </p>
      </div>

      {/* Video + sidebar */}
      <div className="flex gap-4 items-start">
        {/* Video */}
        <div className="relative flex-1 rounded-lg border bg-black aspect-video min-w-0">
          <video
            ref={videoRef}
            key={selectedVideo.video_id}
            src={selectedVideo.video_url}
            controls
            className="h-full w-full"
            disablePictureInPicture
            onTimeUpdate={handleTimeUpdate}
            onSeeked={handleSeeked}
          />

          {activeProposition && (
            <PropositionPopup
              proposition={activeProposition}
              visible={popupVisible}
              onDismiss={handleDismiss}
            />
          )}

          {propositions.length > 0 && (
            <button
              onClick={jumpToNextStatement}
              className="absolute bottom-12 left-1/2 -translate-x-1/2 flex items-center gap-1.5 rounded-full bg-black/60 px-4 py-1.5 text-xs font-medium text-white backdrop-blur-sm border border-white/20 hover:bg-black/80 transition-colors z-10"
            >
              <SkipForward className="size-3.5" />
              Jump to next statement
            </button>
          )}
        </div>

        {/* Propositions sidebar */}
        {sortedPropositions.length > 0 && (
          <div className="flex flex-col gap-2 w-64 shrink-0">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Statements</h3>
            <div className="flex flex-col divide-y divide-border rounded-lg border max-h-[calc(100vh-16rem)] overflow-y-auto">
              {sortedPropositions.map((prop) => {
                const ts = parseTimestamp(prop.start)
                const minutes = Math.floor(ts / 60)
                const seconds = Math.floor(ts % 60)
                const timeLabel = `${minutes}:${String(seconds).padStart(2, "0")}`
                const verdict = prop.verdict?.toLowerCase()
                return (
                  <button
                    key={`${prop.id}-${prop.start}`}
                    onClick={() => jumpToProposition(prop)}
                    className="flex items-start gap-2 px-3 py-2.5 text-left hover:bg-muted/50 transition-colors first:rounded-t-lg last:rounded-b-lg"
                  >
                    <span className="shrink-0 text-[10px] font-mono text-muted-foreground w-8 pt-0.5">{timeLabel}</span>
                    <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                      <span className="text-xs text-foreground leading-snug line-clamp-2">{prop.statement}</span>
                      <span className="text-[10px] text-muted-foreground">{prop.speaker?.name ?? "Unknown"}</span>
                    </div>
                    {verdict && (
                      <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded-full font-medium ${verdict === "true" ? "bg-green-500/15 text-green-600" : verdict === "false" ? "bg-red-500/15 text-red-600" : "bg-yellow-500/15 text-yellow-600"}`}>
                        {verdict === "true" ? "✓" : verdict === "false" ? "✗" : "?"}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Confidence chart */}
      {chartData.length > 1 && (
        <div className="flex flex-col gap-2 rounded-lg border p-4">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Statement Confidence Over Time</h3>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} unit="%" />
              <Tooltip
                contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 6, fontSize: 11 }}
                formatter={(v: number | undefined) => v != null ? [`${v}%`] : ["-"]}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line
                type="monotone"
                dataKey="audio"
                name="Audio"
                stroke="#60a5fa"
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="facial"
                name="Facial"
                stroke="#f472b6"
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
