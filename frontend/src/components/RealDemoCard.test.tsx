import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { RealDemoCard } from "./RealDemoCard";

function CurrentPath() {
  return <output data-testid="path">{useLocation().pathname}</output>;
}

describe("the bundled real-video entry point", () => {
  it("opens the real analysis directly, without starting an upload", () => {
    render(<MemoryRouter><RealDemoCard /><CurrentPath /></MemoryRouter>);
    const entryPoints = screen.getAllByRole("link", { name: "Watch real traffic analysis" });
    for (const link of entryPoints) {
      expect(link).toHaveAttribute("href", "/analysis/real-demo");
    }
    fireEvent.click(entryPoints.at(-1)!);
    expect(screen.getByTestId("path")).toHaveTextContent("/analysis/real-demo");
  });

  it("offers the bundled source clip with visible provenance and scope", () => {
    render(<MemoryRouter><RealDemoCard /></MemoryRouter>);
    expect(screen.getByRole("link", { name: "Download sample video" }))
      .toHaveAttribute("href", "/demos/traffic-source.mp4");
    expect(screen.getByRole("link", { name: "Download sample video" }))
      .toHaveAttribute("download");
    expect(screen.getByRole("link", { name: "Source and credits" }))
      .toHaveAttribute("href", "https://commons.wikimedia.org/wiki/File:E18-Lysaker_(02).ogv");
    expect(screen.getByText(/Kjetil_r, public domain/)).toHaveTextContent(/not a Georgia school study/);
  });
});
