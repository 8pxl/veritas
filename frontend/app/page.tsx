import Hero from "./components/home/hero";
import Logo from "./components/shared/logo";
import Tabbar from "./components/shared/tabbar"

export default function Home() {
  return (
    <main>
      <Tabbar />
      <Hero />
    </main>
  );
}
