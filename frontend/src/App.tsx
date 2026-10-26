import { Link, NavLink, Route, Routes } from "react-router-dom";
import { AnalysisProvider, useAnalysis } from "./state/AnalysisContext";
import { PrintBrief } from "./components/PrintBrief";
import Home from "./pages/Home";
import Analysis from "./pages/Analysis";
import Simulation from "./pages/Simulation";
import NotFound from "./pages/NotFound";
import About from "./pages/About";

function Header() {
  const { analysisId } = useAnalysis();
  return (
    <header className="sticky top-0 z-30 border-b border-rule bg-paper/95 backdrop-blur-sm">
      <div className="mx-auto flex min-h-14 max-w-[1400px] flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 sm:flex-nowrap sm:px-6 sm:py-0">
        <Link to="/" className="flex items-baseline gap-2">
          <span className="font-mono text-[15px] font-semibold tracking-tight text-ink">
            FLOWLAB
          </span>
          <span className="hidden text-[11px] uppercase tracking-[0.18em] text-ink-faint sm:inline">
            traffic digital twin
          </span>
        </Link>
        <nav aria-label="Sections" className="order-last flex w-full items-center gap-1 text-[13px] sm:order-none sm:w-auto">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `rounded px-2.5 py-1.5 transition-colors ${
                isActive ? "bg-accent-soft text-accent" : "text-ink-soft hover:text-ink"
              }`
            }
          >
            Upload
          </NavLink>
          <NavLink
            to={analysisId ? `/analysis/${analysisId}` : "/analysis"}
            className={({ isActive }) =>
              `rounded px-2.5 py-1.5 transition-colors ${
                isActive ? "bg-accent-soft text-accent" : "text-ink-soft hover:text-ink"
              }`
            }
          >
            Analysis
          </NavLink>
          <NavLink
            to={analysisId ? `/simulation/${analysisId}` : "/simulation"}
            className={({ isActive }) =>
              `rounded px-2.5 py-1.5 transition-colors ${
                isActive ? "bg-accent-soft text-accent" : "text-ink-soft hover:text-ink"
              }`
            }
          >
            Simulation
          </NavLink>
          <NavLink to="/about" className={({ isActive }) => `rounded px-2.5 py-1.5 ${isActive ? "bg-accent-soft text-accent" : "text-ink-soft hover:text-ink"}`}>About</NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-4">
          {analysisId && (
            <span className="font-mono text-[11px] text-ink-faint">
              analysis/{analysisId}
            </span>
          )}
          <span
            className="hidden rounded border border-rule px-2 py-1 text-[10px] uppercase tracking-[0.14em] text-ink-faint md:inline"
            title="No face, plate or identity processing. Source footage can still contain identifiable people and plates."
          >
            vehicle tracking only
          </span>
        </div>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="border-t border-rule py-6">
      <div className="mx-auto max-w-[1400px] space-y-1 px-6 text-[11px] leading-relaxed text-ink-faint">
        <p className="mb-2 font-medium text-ink-soft">Created by Shlok Gohil · GA-07 · <Link to="/about" className="underline">About this project</Link></p>
        <p>
          FLOWLAB tracks vehicles, never people: there is no face, plate, identity or
          demographic processing in this application. Every metric is a documented
          calculation over anonymous trajectories, and simulations are hypothetical
          models rather than predictions.
        </p>
        <p>
          The uploaded and annotated videos are kept by the backend and can
          still contain identifiable people or plates, and an anonymous track id does
          not change that. Use Delete on an analysis to remove its files, and only use
          footage you have permission to use. Hosted deployments use private cloud
          storage; local deployments store footage on the backend machine.
          {" "}This app has no account access controls: anyone with access to the
          deployment can open its saved analyses and videos.
        </p>
      </div>
    </footer>
  );
}

function Shell() {
  const { analysisId } = useAnalysis();
  return (
    <div className="flex min-h-full flex-col">
      <a
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:border focus:bg-surface focus:px-3 focus:py-1.5 focus:text-[12px]"
      >
        Skip to content
      </a>
      <Header />
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-8 print:max-w-none print:px-0 print:py-0"
      >
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<About />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/analysis/:analysisId" element={<Analysis />} />
          <Route path="/brief/:analysisId" element={<PrintBrief />} />
          <Route path="/simulation" element={<Simulation />} />
          <Route path="/simulation/:analysisId" element={<Simulation />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
      {analysisId && <AnalysisPicker />}
    </div>
  );
}

/** Quick access to the printable brief for whatever is open. */
function AnalysisPicker() {
  const { analysisId } = useAnalysis();
  return (
    <Link
      to={`/brief/${analysisId}`}
      className="sr-only focus:not-sr-only focus:absolute focus:right-4 focus:top-4 focus:z-50 focus:rounded focus:border focus:bg-surface focus:px-3 focus:py-1.5 focus:text-[12px]"
    >
      Printable analysis brief
    </Link>
  );
}

export default function App() {
  return (
    <AnalysisProvider>
      <Shell />
    </AnalysisProvider>
  );
}
