"use client"

import { useRef, useState, useCallback, useEffect, useMemo } from "react"
import { PropositionsWithAnalysis, useExploreStore } from "../stores/useExploreStore"
import { parseTimestamp, formatTimestamp, DISMISS_AFTER, lerpChartValue } from "./videoPlayerUtils"
import { VideoContainer } from "./VideoContainer"
import { TimestampSidebar } from "./TimestampSidebar"
import { ConfidenceChart, ChartDataPoint } from "./ConfidenceChart"

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
  
  // Interpolated chart data for smooth transitions
  const [interpolatedChartData, setInterpolatedChartData] = useState<ChartDataPoint[]>([])
  const animationFrameRef = useRef<number | null>(null)

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
    [propositions],
  )
  const sortedPropositionsRef = useRef(sortedPropositions)
  useEffect(() => {
    sortedPropositionsRef.current = sortedPropositions
  }, [sortedPropositions])

  const allChartData: ChartDataPoint[] = useMemo(
    () =>
      sortedPropositions.map((prop) => ({
        label: formatTimestamp(parseTimestamp(prop.start)),
        audio:
          prop.audio_confidence?.confidence_score != null
            ? Math.round(prop.audio_confidence.confidence_score * 100)
            : null,
        facial:
          prop.facial_confidence && !prop.facial_confidence.error
            ? Math.round(prop.facial_confidence.confidence_score * 100)
            : null,
      })),
    [sortedPropositions],
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
    setInterpolatedChartData([])
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }
  }, [selectedVideo?.video_id])

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

  // Interpolate chart data based on current video time
  const updateInterpolatedChartData = useCallback(() => {
    if (!videoRef.current || allChartData.length === 0) return

    const currentTime = videoRef.current.currentTime
    const sorted = sortedPropositionsRef.current

    // Find current and next proposition indices
    let currentIndex = -1
    let nextIndex = -1

    for (let i = 0; i < sorted.length; i++) {
      const startTime = parseTimestamp(sorted[i].start)
      if (startTime <= currentTime) {
        currentIndex = i
      } else if (nextIndex === -1) {
        nextIndex = i
        break
      }
    }

    // Build interpolated data
    const newData: ChartDataPoint[] = []

    // Add all points up to current
    for (let i = 0; i <= currentIndex; i++) {
      newData.push(allChartData[i])
    }

    // If there's a next point, interpolate between current and next
    if (currentIndex >= 0 && nextIndex >= 0 && nextIndex < sorted.length) {
      const currentProp = sorted[currentIndex]
      const nextProp = sorted[nextIndex]
      const currentStart = parseTimestamp(currentProp.start)
      const nextStart = parseTimestamp(nextProp.start)

      // Calculate interpolation factor (0 to 1)
      const timeProgress = (currentTime - currentStart) / (nextStart - currentStart)
      const t = Math.max(0, Math.min(1, timeProgress))

      // Interpolate the next point
      const currentData = allChartData[currentIndex]
      const nextData = allChartData[nextIndex]

      const interpolatedPoint: ChartDataPoint = {
        label: nextData.label,
        audio: lerpChartValue(currentData.audio, nextData.audio, t),
        facial: lerpChartValue(currentData.facial, nextData.facial, t),
      }

      newData.push(interpolatedPoint)
    }

    setInterpolatedChartData(newData)
  }, [allChartData])

  // Animation loop for smooth interpolation
  useEffect(() => {
    if (!videoRef.current || !selectedVideo) return

    const animate = () => {
      if (videoRef.current && !videoRef.current.paused) {
        updateInterpolatedChartData()
      }
      animationFrameRef.current = requestAnimationFrame(animate)
    }

    animationFrameRef.current = requestAnimationFrame(animate)

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
        animationFrameRef.current = null
      }
    }
  }, [selectedVideo, updateInterpolatedChartData])

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
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
  }, [])

  const handlePlay = useCallback(() => {
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
    const next = sortedPropositionsRef.current.find(
      (p) => parseTimestamp(p.start) > currentTime + 0.5,
    )
    if (next) {
      videoRef.current.currentTime = parseTimestamp(next.start)
      videoRef.current.play()
    }
  }, [propositions])

  // Sliding window: only show points up to current seek position
  const visibleChartData = allChartData.slice(0, visibleChartCount)
  
  // Use interpolated data if available, otherwise fall back to visible data
  const chartData = interpolatedChartData.length > 0 ? interpolatedChartData : visibleChartData

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
          {selectedPerson?.name ?? ""} &middot; {selectedOrgName ?? ""} &middot;{" "}
          {selectedVideo.time}
        </p>
      </div>

      {/* Video + sidebar */}
      <div className="flex gap-4">
        <VideoContainer
          ref={videoRef}
          containerRef={videoContainerRef}
          videoId={selectedVideo.video_id}
          videoUrl={selectedVideo.video_url}
          activeProposition={activeProposition}
          popupVisible={popupVisible}
          hasPropositions={propositions.length > 0}
          onTimeUpdate={handleTimeUpdate}
          onSeeked={handleSeeked}
          onPause={handlePause}
          onPlay={handlePlay}
          onDismiss={handleDismiss}
          onJumpNext={jumpToNextStatement}
        />

        {sortedPropositions.length > 0 && (
          <TimestampSidebar
            ref={sidebarRef}
            propositions={sortedPropositions}
            activeProposition={activeProposition}
            onJumpTo={jumpToProposition}
          />
        )}
      </div>

      {/* Sliding-window confidence chart */}
      <ConfidenceChart data={chartData} />
    </div>
  )
}
