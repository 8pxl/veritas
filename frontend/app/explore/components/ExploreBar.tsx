"use client"

import { useEffect, useState, useCallback } from "react"
import {
  Building2,
  ChevronRight,
  User,
  Video as VideoIcon,
  Loader2,
} from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { useExploreStore } from "../stores/useExploreStore"
import { listPeoplePeopleGet, getPropositionsByPersonPeoplePersonIdPropositionsGet } from "@/lib/client/sdk.gen"
import type { Person, Proposition, Video, Organization } from "@/lib/client/types.gen"

interface OrgGroup {
  org: Organization
  people: Person[]
}

interface PersonPropositions {
  propositions: Proposition[]
  videos: Video[]
  loading: boolean
  loaded: boolean
}

export function ExploreBar() {
  const { selectedVideo, selectVideo } = useExploreStore()
  const [orgGroups, setOrgGroups] = useState<OrgGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [personData, setPersonData] = useState<Record<string, PersonPropositions>>({})

  // Fetch all people on mount and group by organization
  useEffect(() => {
    async function fetchPeople() {
      try {
        setLoading(true)
        const response = await listPeoplePeopleGet()
        const people = response.data ?? []

        // Group people by organization id
        const orgMap = new Map<number, OrgGroup>()
        for (const person of people) {
          const orgId = person.organization.id
          if (!orgMap.has(orgId)) {
            orgMap.set(orgId, { org: person.organization, people: [] })
          }
          orgMap.get(orgId)!.people.push(person)
        }

        setOrgGroups(Array.from(orgMap.values()))
        setError(null)
      } catch (err) {
        console.error("Failed to fetch people:", err)
        setError("Failed to load data")
      } finally {
        setLoading(false)
      }
    }

    fetchPeople()
  }, [])

  // Fetch propositions for a person (lazy, on expand)
  const fetchPersonPropositions = useCallback(async (personId: string) => {
    // Skip if already loaded or currently loading
    setPersonData((prev) => {
      if (prev[personId]?.loaded || prev[personId]?.loading) return prev
      return { ...prev, [personId]: { propositions: [], videos: [], loading: true, loaded: false } }
    })

    // Check again outside setState
    if (personData[personId]?.loaded || personData[personId]?.loading) return

    try {
      const response = await getPropositionsByPersonPeoplePersonIdPropositionsGet({
        path: { person_id: personId },
      })
      const propositions = response.data ?? []

      // Extract unique videos from propositions
      const videoMap = new Map<string, Video>()
      for (const prop of propositions) {
        if (!videoMap.has(prop.video.video_id)) {
          videoMap.set(prop.video.video_id, prop.video)
        }
      }

      setPersonData((prev) => ({
        ...prev,
        [personId]: {
          propositions,
          videos: Array.from(videoMap.values()),
          loading: false,
          loaded: true,
        },
      }))
    } catch (err) {
      console.error(`Failed to fetch propositions for person ${personId}:`, err)
      setPersonData((prev) => ({
        ...prev,
        [personId]: { propositions: [], videos: [], loading: false, loaded: true },
      }))
    }
  }, [personData])

  const handleVideoClick = useCallback((video: Video, person: Person, orgName: string, personId: string) => {
    const data = personData[personId]
    if (!data) return
    // Filter propositions that belong to this video
    const videoPropositions = data.propositions.filter((p) => p.video.video_id === video.video_id)
    selectVideo(video, person, orgName, videoPropositions)
  }, [personData, selectVideo])

  return (
    <Sidebar variant="floating" collapsible="offcanvas">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <div>
                <div className="bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                  <VideoIcon className="size-4" />
                </div>
                <div className="flex flex-col gap-0.5 leading-none">
                  <span className="font-semibold">Explore</span>
                  <span className="text-xs">Video Analysis</span>
                </div>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Organizations</SidebarGroupLabel>
          <SidebarGroupContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="size-5 animate-spin text-muted-foreground" />
              </div>
            ) : error ? (
              <div className="px-3 py-4 text-sm text-destructive">{error}</div>
            ) : orgGroups.length === 0 ? (
              <div className="px-3 py-4 text-sm text-muted-foreground">No data available</div>
            ) : (
              <SidebarMenu>
                {orgGroups.map((group) => (
                  <Collapsible key={group.org.id} asChild defaultOpen>
                    <SidebarMenuItem>
                      <CollapsibleTrigger asChild>
                        <SidebarMenuButton tooltip={group.org.name}>
                          <Building2 />
                          <span>{group.org.name}</span>
                          <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                        </SidebarMenuButton>
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <SidebarMenuSub>
                          {group.people.map((person) => (
                            <Collapsible key={person.id} asChild onOpenChange={(open) => { if (open) fetchPersonPropositions(person.id) }}>
                              <SidebarMenuSubItem>
                                <CollapsibleTrigger asChild>
                                  <SidebarMenuSubButton className="truncate">
                                    <User className="size-3.5" />
                                    <span>{person.name}</span>
                                    <span className="ml-auto text-[10px] text-muted-foreground">{person.position ?? ""}</span>
                                  </SidebarMenuSubButton>
                                </CollapsibleTrigger>
                                <CollapsibleContent>
                                  <SidebarMenuSub>
                                    {personData[person.id]?.loading ? (
                                      <SidebarMenuSubItem>
                                        <div className="flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground">
                                          <Loader2 className="size-3 animate-spin" />
                                          <span>Loading...</span>
                                        </div>
                                      </SidebarMenuSubItem>
                                    ) : personData[person.id]?.videos.length === 0 ? (
                                      <SidebarMenuSubItem>
                                        <div className="px-2 py-1.5 text-xs text-muted-foreground">No videos</div>
                                      </SidebarMenuSubItem>
                                    ) : (
                                      personData[person.id]?.videos.map((video) => (
                                        <SidebarMenuSubItem key={video.video_id}>
                                          <SidebarMenuSubButton data-active={selectedVideo?.video_id === video.video_id} onClick={() => handleVideoClick(video, person, group.org.name, person.id)} className="cursor-pointer">
                                            <VideoIcon className="size-3" />
                                            <span>{video.title}</span>
                                          </SidebarMenuSubButton>
                                        </SidebarMenuSubItem>
                                      ))
                                    )}
                                  </SidebarMenuSub>
                                </CollapsibleContent>
                              </SidebarMenuSubItem>
                            </Collapsible>
                          ))}
                        </SidebarMenuSub>
                      </CollapsibleContent>
                    </SidebarMenuItem>
                  </Collapsible>
                ))}
              </SidebarMenu>
            )}
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarRail />
    </Sidebar>
  )
}
