import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-lg py-20 text-center">
      <p className="font-mono text-[13px] text-ink-faint">404</p>
      <h1 className="mt-2 text-2xl font-medium text-ink">This page does not exist</h1>
      <p className="mt-2 text-[13px] text-ink-soft">
        Start from the upload page to analyse a traffic video, or open the demo
        dataset.
      </p>
      <Link
        to="/"
        className="mt-6 inline-block rounded border border-ink bg-ink px-4 py-2 text-[13px] text-paper"
      >
        Back to upload
      </Link>
    </div>
  );
}
