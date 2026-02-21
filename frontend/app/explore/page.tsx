import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import Tabbar from "../components/shared/tabbar";
import { ExploreBar } from "./components/ExploreBar";
import { VideoPlayer } from "./components/VideoPlayer";

export default function Home() {
  return (
    <main>
      <Tabbar />
      <SidebarProvider>
        <ExploreBar />
        <SidebarInset >
          <div className="flex flex-1 flex-col gap-4 p-4">
            <VideoPlayer />
          </div>
        </SidebarInset>
      </SidebarProvider >
    </main >
  );
}
