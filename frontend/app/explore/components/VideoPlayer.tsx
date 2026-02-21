"use client"

import { useRef, useState, useCallback, useEffect } from "react"
import { useExploreStore } from "../stores/useExploreStore"
import { ConfidencePopup } from "./ConfidencePopup"
import type { LowConfidenceMoment } from "@/app/types"

const TRIGGER_WINDOW = 1.5 // seconds — how close to a timestamp before triggering
const DISMISS_AFTER = 8 // seconds — auto-dismiss if not manually closed

export function VideoPlayer() {
  const { selectedVideo, selectedPersonName, selectedCompanyName } = useExploreStore()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [activeMoment, setActiveMoment] = useState<LowConfidenceMoment | null>(null)
  const [popupVisible, setPopupVisible] = useState(false)
  const triggeredRef = useRef<Set<number>>(new Set())
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Reset triggered set when video changes
  useEffect(() => {
    triggeredRef.current.clear()
    setActiveMoment(null)
    setPopupVisible(false)
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
  }, [selectedVideo?.id])

  const handleTimeUpdate = useCallback(() => {
    if (!videoRef.current || !selectedVideo) return
    const currentTime = videoRef.current.currentTime
    const moments = selectedVideo.analysisData.lowConfidenceMoments

    for (const moment of moments) {
      if (triggeredRef.current.has(moment.timestamp)) continue

      if (
        currentTime >= moment.timestamp &&
        currentTime <= moment.timestamp + TRIGGER_WINDOW
      ) {
        triggeredRef.current.add(moment.timestamp)
        setActiveMoment(moment)
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
  }, [selectedVideo])

  // Allow re-triggering when user seeks backward past a moment
  const handleSeeked = useCallback(() => {
    if (!videoRef.current || !selectedVideo) return
    const currentTime = videoRef.current.currentTime

    // Re-enable any moments that are ahead of the current time
    for (const moment of selectedVideo.analysisData.lowConfidenceMoments) {
      if (currentTime < moment.timestamp) {
        triggeredRef.current.delete(moment.timestamp)
      }
    }
  }, [selectedVideo])

  const handleDismiss = useCallback(() => {
    setPopupVisible(false)
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
  }, [])

  if (!selectedVideo) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <p>Select a video from the sidebar to begin analysis.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-semibold">{selectedVideo.title}</h2>
        <p className="text-sm text-muted-foreground">
          {selectedPersonName} &middot; {selectedCompanyName} &middot; {selectedVideo.date}
        </p>
      </div>

      <div className="relative w-full overflow-hidden rounded-lg border bg-black aspect-video">
        <video
          ref={videoRef}
          key={selectedVideo.id}
          src={selectedVideo.videoUrl}
          controls
          className="h-full w-full"
          disablePictureInPicture
          onTimeUpdate={handleTimeUpdate}
          onSeeked={handleSeeked}
        />

        {activeMoment && (
          <ConfidencePopup
            moment={activeMoment}
            visible={popupVisible}
            onDismiss={handleDismiss}
          />
        )}
      </div>
    </div>
  )
}
