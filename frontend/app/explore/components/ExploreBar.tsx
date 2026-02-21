"use client"

import {
  Building2,
  ChevronRight,
  User,
  Video,
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
import { mockCompanies } from "@/app/mockData"
import { useExploreStore } from "../stores/useExploreStore"

export function ExploreBar() {
  const { selectedVideo, selectVideo } = useExploreStore()

  return (
    <Sidebar variant="floating" collapsible="offcanvas">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <div>
                <div className="bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                  <Video className="size-4" />
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
          <SidebarGroupLabel>Companies</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {mockCompanies.map((company) => (
                <Collapsible key={company.id} asChild defaultOpen>
                  <SidebarMenuItem>
                    <CollapsibleTrigger asChild>
                      <SidebarMenuButton tooltip={company.name}>
                        <Building2 />
                        <span>{company.name}</span>
                        <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                      </SidebarMenuButton>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <SidebarMenuSub>
                        {company.people.map((person) => (
                          <Collapsible key={person.id} asChild defaultOpen>
                            <SidebarMenuSubItem>
                              <CollapsibleTrigger asChild>
                                <SidebarMenuSubButton className="truncate">
                                  <User className="size-3.5" />
                                  <span>{person.name}</span>
                                  <span className="ml-auto text-[10px] text-muted-foreground">{person.role}</span>
                                </SidebarMenuSubButton>
                              </CollapsibleTrigger>
                              <CollapsibleContent>
                                <SidebarMenuSub>
                                  {person.videos.map((video) => (
                                    <SidebarMenuSubItem key={video.id}>
                                      <SidebarMenuSubButton
                                        data-active={selectedVideo?.id === video.id}
                                        onClick={() => selectVideo(video, person.name, company.name)}
                                        className="cursor-pointer"
                                      >
                                        <Video className="size-3" />
                                        <span>{video.title}</span>
                                      </SidebarMenuSubButton>
                                    </SidebarMenuSubItem>
                                  ))}
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
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarRail />
    </Sidebar>
  )
}
