import { Link } from "react-router-dom";
import { Label, Panel } from "./Primitives";

export function RealDemoCard() {
  return (
    <Panel className="mb-10 overflow-hidden">
      <div className="grid md:grid-cols-[1fr_1.1fr]">
        <Link to="/analysis/real-demo" aria-label="Watch real traffic analysis" className="block bg-ink">
          <img src="/demos/traffic-poster.jpg" alt="Real cars and buses on the E18 road in Lysaker, Norway" className="h-full max-h-[300px] w-full object-cover" />
        </Link>
        <div className="flex flex-col justify-center p-6">
          <Label>Real footage · ready to explore</Label>
          <h2 className="mt-2 text-[23px] font-medium leading-tight text-ink">From a real road to an explainable traffic model.</h2>
          <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
            Follow actual vehicles through detection, tracking and measurement. This
            precomputed example opens without an upload or a processing queue.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link to="/analysis/real-demo" className="rounded border border-ink bg-ink px-4 py-2 text-[13px] font-medium text-paper hover:bg-ink-soft">Watch real traffic analysis</Link>
            <a href="/demos/traffic-source.mp4" download="flowlab-real-traffic.mp4" className="rounded border border-rule px-4 py-2 text-[13px] text-ink-soft hover:border-ink-faint">Download sample video</a>
          </div>
          <p className="mt-4 text-[11px] leading-relaxed text-ink-faint">
            Public-road footage from Norway, not a Georgia school study. Video by
            Kjetil_r, public domain. Stabilized and resized for this example.{" "}
            <a href="https://commons.wikimedia.org/wiki/File:E18-Lysaker_(02).ogv" target="_blank" rel="noreferrer" className="underline">Source and credits</a>
          </p>
        </div>
      </div>
    </Panel>
  );
}
