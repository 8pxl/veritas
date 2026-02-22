"use client"

import { useRef, useState, useCallback, useEffect, useMemo } from "react"
import { PropositionsWithAnalysis, useExploreStore } from "../stores/useExploreStore"
import { PropositionPopup, AudioEmotionOverlay } from "./ConfidencePopup"
import { SkipForward } from "lucide-react"
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts"

const DISMISS_AFTER = 8

function parseTimestamp(verifyAt: string): number {
  const num = Number(verifyAt)
  if (!isNaN(num)) return num
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
  const popupVisibleRef = useRef(false)
  const triggeredRef = useRef<Set<number>>(new Set())
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sidebar highlight + chart sliding window
  const activeSidebarIdRef = useRef<number | null>(null)
  const [activeSidebarId, setActiveSidebarId] = useState<number | null>(null)
  const visibleChartCountRef = useRef(0)
  const [visibleChartCount, setVisibleChartCount] = useState(0)

  // Ref to active sidebar row for auto-scroll
  const activeRowRef = useRef<HTMLButtonElement | null>(null)
  // Refs for same-height layout
  const videoContainerRef = useRef<HTMLDivElement>(null)
  const sidebarRef = useRef<HTMLDivElement>(null)

  // Sync sidebar height to video container height
  useEffect(() => {
    function onResize() {
      const el = videoContainerRef.current
      if (!el) return
      if (sidebarRef.current) {
        sidebarRef.current.style.maxHeight = `${el.offsetHeight}px`
      }
    }
    window.addEventListener("resize", onResize)
    onResize()
    return () => window.removeEventListener("resize", onResize)
  })

  const sortedPropositions = useMemo(
    () => [...propositions].sort((a, b) => parseTimestamp(a.start) - parseTimestamp(b.start)),
    [propositions]
  )
  const sortedPropositionsRef = useRef(sortedPropositions)
  useEffect(() => { sortedPropositionsRef.current = sortedPropositions }, [sortedPropositions])

  const allChartData = useMemo(() =>
    sortedPropositions.map((prop) => {
      const ts = parseTimestamp(prop.start)
      const m = Math.floor(ts / 60)
      const s = Math.floor(ts % 60)
      return {
        label: `${m}:${String(s).padStart(2, "0")}`,
        audio: prop.audio_confidence?.confidence_score != null
          ? Math.round(prop.audio_confidence.confidence_score * 100)
          : null,
        facial: prop.facial_confidence && !prop.facial_confidence.error
          ? Math.round(prop.facial_confidence.confidence_score * 100)
          : null,
      }
    }),
    [sortedPropositions]
  )

  // Reset everything on video change
  useEffect(() => {
    triggeredRef.current.clear()
    setActiveProposition(null)
    setPopupVisible(false)
    popupVisibleRef.current = false
    activeSidebarIdRef.current = null
    setActiveSidebarId(null)
    visibleChartCountRef.current = 0
    setVisibleChartCount(0)
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
  }, [selectedVideo?.video_id])

  // Auto-scroll the highlighted list item into view
  useEffect(() => {
    activeRowRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" })
  }, [activeProposition?.id])

  const updateTimeTracking = useCallback((currentTime: number) => {
    const sorted = sortedPropositionsRef.current
    let newActiveId: number | null = null
    let newCount = 0
    for (const prop of sorted) {
      if (parseTimestamp(prop.start) <= currentTime) {
        newActiveId = prop.id
        newCount++
      } else {
        break
      }
    }
    if (newActiveId !== activeSidebarIdRef.current) {
      activeSidebarIdRef.current = newActiveId
      setActiveSidebarId(newActiveId)
    }
    if (newCount !== visibleChartCountRef.current) {
      visibleChartCountRef.current = newCount
      setVisibleChartCount(newCount)
    }
  }, [])

  const handleTimeUpdate = useCallback(() => {
    if (!videoRef.current || !selectedVideo || propositions.length === 0) return
    const currentTime = videoRef.current.currentTime

    updateTimeTracking(currentTime)

    for (const prop of propositions) {
      const ts = parseTimestamp(prop.start)
      const end = parseTimestamp(prop.end)
      if (triggeredRef.current.has(prop.id)) continue
      if (currentTime >= ts && currentTime <= end) {
        triggeredRef.current.add(prop.id)
        setActiveProposition(prop)
        setPopupVisible(true)
        popupVisibleRef.current = true
        if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
        dismissTimerRef.current = setTimeout(() => {
          setPopupVisible(false)
          popupVisibleRef.current = false
        }, DISMISS_AFTER * 1000)
        break
      }
    }
  }, [selectedVideo, propositions, updateTimeTracking])

  const handleSeeked = useCallback(() => {
    if (!videoRef.current) return
    const currentTime = videoRef.current.currentTime
    for (const prop of sortedPropositionsRef.current) {
      if (parseTimestamp(prop.start) > currentTime) {
        triggeredRef.current.delete(prop.id)
      }
    }
    updateTimeTracking(currentTime)
  }, [updateTimeTracking])

  const handleDismiss = useCallback(() => {
    setPopupVisible(false)
    popupVisibleRef.current = false
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
  }, [])

  const handlePause = useCallback(() => {
    // Cancel auto-dismiss while paused so popup lingers
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
  }, [])

  const handlePlay = useCallback(() => {
    // Restart dismiss timer if popup is still showing
    if (popupVisibleRef.current) {
      if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = setTimeout(() => {
        setPopupVisible(false)
        popupVisibleRef.current = false
      }, DISMISS_AFTER * 1000)
    }
  }, [])

  const jumpToProposition = useCallback((prop: PropositionsWithAnalysis) => {
    if (!videoRef.current) return
    triggeredRef.current.delete(prop.id)
    videoRef.current.currentTime = parseTimestamp(prop.start)
    videoRef.current.play()
    setActiveProposition(prop)
    setPopupVisible(true)
    popupVisibleRef.current = true
    if (dismissTimerRef.current) clearTimeout(dismissTimerRef.current)
    dismissTimerRef.current = setTimeout(() => {
      setPopupVisible(false)
      popupVisibleRef.current = false
    }, DISMISS_AFTER * 1000)
  }, [])

  const jumpToNextStatement = useCallback(() => {
    if (!videoRef.current || propositions.length === 0) return
    const currentTime = videoRef.current.currentTime
    const next = sortedPropositionsRef.current.find((p) => parseTimestamp(p.start) > currentTime + 0.5)
    if (next) {
      videoRef.current.currentTime = parseTimestamp(next.start)
      videoRef.current.play()
    }
  }, [propositions])

  // Sliding window: only show points up to current seek position
  const visibleChartData = allChartData.slice(0, visibleChartCount)

  if (!selectedVideo) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <p>Select a video from the sidebar to begin analysis.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-4">
      {/* Title */}
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-semibold">{selectedVideo.title}</h2>
        <p className="text-sm text-muted-foreground">
          {selectedPerson?.name ?? ""} &middot; {selectedOrgName ?? ""} &middot; {selectedVideo.time}
        </p>
      </div>

      {/* Video + sidebar — same height via flex stretch */}
      <div className="flex gap-4">
        {/* Video */}
        <div ref={videoContainerRef} className="relative flex-1 rounded-lg border bg-black aspect-video min-w-0 self-start">
          <video
            ref={videoRef}
            key={selectedVideo.video_id}
            src={selectedVideo.video_url}
            controls
            className="h-full w-full"
            disablePictureInPicture
            onTimeUpdate={handleTimeUpdate}
            onSeeked={handleSeeked}
            onPause={handlePause}
            onPlay={handlePlay}
          />
          {activeProposition && (
            <PropositionPopup
              proposition={activeProposition}
              visible={popupVisible}
              onDismiss={handleDismiss}
            />
          )}
          {activeProposition && (
            <AudioEmotionOverlay
              proposition={activeProposition}
              visible={popupVisible}
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

        {/* Propositions sidebar — height synced to video via ResizeObserver */}
        {sortedPropositions.length > 0 && (
          <div
            ref={sidebarRef}
            className="w-64 shrink-0 flex flex-col rounded-lg border overflow-hidden self-start"
          >
            <div className="flex-1 overflow-y-auto divide-y divide-border flex flex-col">
              {sortedPropositions.map((prop) => {
                const ts = parseTimestamp(prop.start)
                const minutes = Math.floor(ts / 60)
                const seconds = Math.floor(ts % 60)
                const timeLabel = `${minutes}:${String(seconds).padStart(2, "0")}`
                const verdict = prop.verdict?.toLowerCase()
                const isActive = prop.start === activeProposition?.start
                return (
                  <button
                    key={`${prop.id}-${prop.start}`}
                    ref={isActive ? activeRowRef : null}
                    onClick={() => jumpToProposition(prop)}
                    className={`flex items-start gap-2 px-3 py-2.5 text-left transition-all shrink-0 ${
                      isActive
                        ? "bg-accent/15 border-l-4 border-accent pl-2"
                        : "hover:bg-muted/50 border-l-4 border-transparent pl-2"
                    }`}
                  >
                    <span className={`shrink-0 text-[10px] font-mono w-8 pt-0.5 ${isActive ? "text-accent font-bold" : "text-muted-foreground"}`}>
                      {timeLabel}
                    </span>
                    <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                      <span className={`text-xs leading-snug line-clamp-2 ${isActive ? "text-accent font-semibold" : "text-foreground"}`}>
                        {prop.statement}
                      </span>
                      <span className="text-[10px] text-muted-foreground">{prop.speaker?.name ?? "Unknown"}</span>
                    </div>
                    {verdict && (
                      <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                        verdict === "true" ? "bg-green-500/15 text-green-600" :
                        verdict === "false" ? "bg-red-500/15 text-red-600" :
                        "bg-yellow-500/15 text-yellow-600"
                      }`}>
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

      {/* Sliding-window confidence chart */}
      {allChartData.length > 1 && (
        <div className="flex flex-col gap-2 rounded-lg border p-4">
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart
              data={visibleChartData}
              margin={{ top: 4, right: 8, left: -16, bottom: 0 }}
            >
              <defs>
                <linearGradient id="colorAudio" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#894048" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#894048" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="label" hide />
              <YAxis domain={[0, 100]} hide />
              <Tooltip
                contentStyle={{ fontSize: 11, background: "#FFF4E9", border: "1px solid #894048", borderRadius: 6 }}
                formatter={(v) => [`${v ?? ""}%`]}
              />
              <Area
                type="monotone"
                dataKey="audio"
                name="Audio"
                stroke="#894048"
                strokeWidth={2}
                fill="url(#colorAudio)"
                dot={false}
                connectNulls
                isAnimationActive
                animationDuration={400}
                animationEasing="ease-out"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
