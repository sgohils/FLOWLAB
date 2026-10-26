import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import About from "./About";

function CurrentPath() {
  return <output data-testid="path">{useLocation().pathname}</output>;
}

describe("the project explanation", () => {
  it("keeps real footage and the synthetic sandbox as distinct destinations", () => {
    render(<MemoryRouter initialEntries={["/about"]}><About /><CurrentPath /></MemoryRouter>);
    fireEvent.click(screen.getByRole("link", { name: "Explore real footage" }));
    expect(screen.getByTestId("path")).toHaveTextContent("/analysis/real-demo");
    fireEvent.click(screen.getByRole("link", { name: "Synthetic queue sandbox" }));
    expect(screen.getByTestId("path")).toHaveTextContent(/^\/analysis\/demo$/);
  });

  it("identifies the creator and provides the media and assistance records", () => {
    render(<MemoryRouter><About /></MemoryRouter>);
    expect(screen.getByText(/Created by Shlok Gohil/))
      .toHaveTextContent("Georgia's 7th Congressional District");
    expect(screen.getByRole("link", { name: "Video credits" }))
      .toHaveAttribute("href", "/demos/CREDITS.txt");
    expect(screen.getByRole("link", { name: "AI assistance record" }))
      .toHaveAttribute("href", "https://github.com/sgohils/FLOWLAB/blob/main/docs/AI_ASSISTANCE.md");
    expect(screen.getByText(/a public-domain roadway clip by Kjetil_r/))
      .toHaveTextContent(/not measured results from a local school/);
  });
});
