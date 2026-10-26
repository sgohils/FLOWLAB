import { Link } from "react-router-dom";
import { Label, Panel, Section } from "../components/Primitives";

const PIPELINE = [
  ["Detect", "A pretrained YOLO model locates cars, buses, trucks, motorcycles and bicycles. It is not trained to identify people or read number plates."],
  ["Track", "ByteTrack links sightings into anonymous vehicle paths. Tracking gaps stay unknown rather than being filled with invented movement."],
  ["Measure", "Geometry and timestamps produce queue counts, crossing rates and slow-time estimates. Each headline metric exposes its definition and evidence."],
  ["Compare", "A corridor model replays arrivals as a baseline, then changes one assumption. The interface separates model error from a scenario's effect."],
];

export default function About() {
  return <div className="mx-auto max-w-4xl">
    <Label>The project</Label>
    <h1 className="mt-2 text-3xl font-medium tracking-tight text-ink">Small traffic decisions deserve visible evidence.</h1>
    <p className="mt-4 text-[15px] leading-relaxed text-ink-soft">FLOWLAB helps school transport teams and community planners inspect traffic video and explore hypothetical changes before deciding what to investigate on site.</p>
    <p className="mt-3 font-mono text-[12px] text-ink-faint">Created by Shlok Gohil · Georgia's 7th Congressional District</p>
    <div className="mb-10 mt-7 flex flex-wrap gap-3">
      <Link to="/analysis/real-demo" className="rounded bg-ink px-4 py-2 text-[13px] text-paper">Explore real footage</Link>
      <Link to="/analysis/demo" className="rounded border border-rule px-4 py-2 text-[13px] text-ink-soft">Synthetic queue sandbox</Link>
    </div>
    <Section title="How it works">
      <div className="grid gap-4 md:grid-cols-2">{PIPELINE.map(([title, text], index) => <Panel key={title} className="p-5">
        <Label>0{index + 1} · {title}</Label><p className="mt-3 text-[13px] leading-relaxed text-ink-soft">{text}</p>
      </Panel>)}</div>
    </Section>
    <Section title="What the examples show">
      <Panel className="space-y-3 p-5 text-[13px] leading-relaxed text-ink-soft">
        <p><b className="text-ink">Real video:</b> a public-domain roadway clip by Kjetil_r, filmed in Lysaker, Norway. Detection output is precomputed with the same pipeline used for uploads. It demonstrates the software, not measured results from a local school.</p>
        <p><b className="text-ink">Synthetic sandbox:</b> a reproducible queue with known, simulated trajectories. It makes the scenario controls easy to inspect. It is labeled synthetic throughout.</p>
        <p><b className="text-ink">Limits:</b> tracking can miss, split or merge vehicles. Motion is measured in image coordinates. Scenario outcomes are model outputs and require field validation before operational decisions.</p>
        <p><b className="text-ink">Shared access:</b> this demo has no sign-in or per-user access control. Other visitors can open saved analyses and footage. Use the public-domain example here and run locally for private school footage.</p>
      </Panel>
    </Section>
    <Section title="Built to be inspected">
      <Panel className="space-y-3 p-5 text-[13px] leading-relaxed text-ink-soft">
        <p>Python, FastAPI, OpenCV, Ultralytics YOLO and ByteTrack power the backend. React, TypeScript and Vite power the interface. The application supports local storage and hosted PostgreSQL, private Blob storage and queued processing.</p>
        <p>AI tools assisted implementation, debugging, tests and documentation. The repository includes an assistance record and a contribution worksheet for the submission.</p>
        <div className="flex flex-wrap gap-4 text-accent underline">
          <a href="https://github.com/sgohils/FLOWLAB" target="_blank" rel="noreferrer">Source code</a>
          <a href="https://github.com/sgohils/FLOWLAB/blob/main/docs/AI_ASSISTANCE.md" target="_blank" rel="noreferrer">AI assistance record</a>
          <a href="/demos/CREDITS.txt">Video credits</a>
        </div>
      </Panel>
    </Section>
  </div>;
}
