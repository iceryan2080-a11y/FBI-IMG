import Navbar from "./components/Navbar.jsx";
import Hero from "./components/Hero.jsx";
import AnalyzerPanel from "./components/AnalyzerPanel.jsx";
import ModeCards from "./components/ModeCards.jsx";
import Architecture from "./components/Architecture.jsx";
import Footer from "./components/Footer.jsx";

export default function App() {
  return (
    <>
      <Navbar />
      <Hero />
      <main>
        <AnalyzerPanel />
        <ModeCards />
        <Architecture />
      </main>
      <Footer />
    </>
  );
}
