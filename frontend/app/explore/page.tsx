import { SidebarProvider } from "@/components/ui/sidebar";
import Tabbar from "../components/shared/tabbar"
import { ExploreBar } from "./components/ExploreBar";
export default function Home() {
  return (
    <main>
      <Tabbar />
      <SidebarProvider>
        <div>
          <ExploreBar>
          </ExploreBar>
        </div>
      </SidebarProvider>
    </main>
  );
}
