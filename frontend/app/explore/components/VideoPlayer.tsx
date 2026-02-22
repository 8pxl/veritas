"use client"

import { useRef, useState, useCallback, useEffect } from "react"
import { useExploreStore } from "../stores/useExploreStore"
import { PropositionPopup } from "./ConfidencePopup"
import type { Proposition } from "@/lib/client/types.gen"

const TRIGGER_WINDOW = 1.5 // seconds — how close to a timestamp before triggering
const DISMISS_AFTER = 8 // seconds — auto-dismiss if not manually closed

/** Parse verifyAt string to seconds. Supports "MM:SS", "HH:MM:SS", or raw number. */
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
  const [activeProposition, setActiveProposition] = useState<Proposition | null>(null)
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
      const ts = parseTimestamp(prop.verifyAt)
      if (triggeredRef.current.has(prop.id)) continue

      if (currentTime >= ts && currentTime <= ts + TRIGGER_WINDOW) {
        triggeredRef.current.add(prop.id)
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
      const ts = parseTimestamp(prop.verifyAt)
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

  if (!selectedVideo) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <p>Select a video from the sidebar to begin analysis.</p>
      </div>
    )
  }

  const transformedUrl = () => {
    if (selectedVideo.video_url.includes("youtube.com") || selectedVideo.video_url.includes("youtu.be")) {
      // https://vid.totsuki.harvey-l.com/<VIDEO_ID>.webm or .mp4
      return `https://vid.totsuki.harvey-l.com/${selectedVideo.video_id}.webm`
    }
    return selectedVideo.video_url
  }

  console.log("Transformed video URL:", transformedUrl())

  return (
    <div className="flex flex-1 flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-semibold">{selectedVideo.title}</h2>
        <p className="text-sm text-muted-foreground">{selectedPerson?.name ?? ""} &middot; {selectedOrgName ?? ""} &middot; {selectedVideo.time}</p>
      </div>

      <div className="relative w-full overflow-hidden rounded-lg border bg-black aspect-video">
        <video ref={videoRef} key={selectedVideo.video_id} src={transformedUrl()} controls className="h-full w-full" disablePictureInPicture onTimeUpdate={handleTimeUpdate} onSeeked={handleSeeked} />

        {activeProposition && (
          <PropositionPopup
            proposition={activeProposition}
            visible={popupVisible}
            onDismiss={handleDismiss}
          />
        )}
      </div>
    </div>
  )
}
