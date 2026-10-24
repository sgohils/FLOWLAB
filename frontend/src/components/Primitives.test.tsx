import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Button, Label, Notice, Panel, Pill, Row, Section } from "./Primitives";

/**
 * The design atoms, asserted on the three things that actually matter to a
 * caller: the text, the tone class, and whether a control responds.
 */
describe("Row", () => {
  it("shows the label as a term and the value as its definition", () => {
    render(
      <dl>
        <Row label="Mean wait" value="12.3 s" />
      </dl>,
    );
    expect(screen.getByText("Mean wait").tagName).toBe("DT");
    expect(screen.getByText("12.3 s").tagName).toBe("DD");
    // roomy variant: the surrounding list supplies the size
    expect(screen.getByText("Mean wait")).toHaveClass("text-ink-faint");
    expect(screen.getByText("Mean wait")).not.toHaveClass("text-[11px]");
    expect(screen.getByText("12.3 s")).toHaveClass("font-mono", "text-ink");
  });


  it("switches to the dense treatment when asked", () => {
    render(
      <dl>
        <Row label="Vehicles" value="41" dense />
      </dl>,
    );
    expect(screen.getByText("Vehicles")).toHaveClass("text-[11px]", "text-ink-faint");
    expect(screen.getByText("41")).toHaveClass("font-mono", "text-ink", "text-[12px]");
  });

  it("renders an em dash for a value that is missing", () => {
    render(
      <dl>
        <Row label="Throughput" value="—" />
      </dl>,
    );
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("Pill", () => {
  it("uses the neutral tone unless one is given", () => {
    render(<Pill>demo</Pill>);
    expect(screen.getByText("demo")).toHaveClass("border-rule", "text-ink-faint");
  });

  it("applies the tone it is given", () => {
    render(<Pill tone="caution">stale</Pill>);
    expect(screen.getByText("stale")).toHaveClass("border-caution/30", "text-caution");
  });
});

describe("Label", () => {
  it("is small, uppercase and tracked-out", () => {
    render(<Label>Evidence</Label>);
    expect(screen.getByText("Evidence")).toHaveClass("uppercase", "text-ink-faint");
  });
});

describe("Notice", () => {
  it("shows its title as a heading for the message", () => {
    render(
      <Notice title="Thin evidence">
        <p>Treat the numbers as indicative.</p>
      </Notice>,
    );
    expect(screen.getByText("Thin evidence")).toBeInTheDocument();
    expect(screen.getByText("Treat the numbers as indicative.")).toBeInTheDocument();
  });

  it("carries the tone as a class, not as colour alone", () => {
    render(<Notice tone="error">Failed</Notice>);
    expect(screen.getByText("Failed")).toHaveClass("border-red-300", "text-red-800");
  });
});

describe("Button", () => {
  it("calls its handler when clicked, and not at all while disabled", async () => {
    const onClick = vi.fn();
    const { rerender } = render(<Button onClick={onClick}>Choose video</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Choose video" }));
    expect(onClick).toHaveBeenCalledTimes(1);

    rerender(
      <Button onClick={onClick} disabled>
        Choose video
      </Button>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Choose video" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("defaults to type=button so it cannot submit a form by accident", () => {
    render(<Button>Run</Button>);
    expect(screen.getByRole("button", { name: "Run" })).toHaveAttribute("type", "button");
  });
});

describe("Panel and Section", () => {
  it("forwards the id, role and label a landmark needs", () => {
    render(
      <Panel role="group" aria-label="Threshold events" id="events">
        <p>inside</p>
      </Panel>,
    );
    const panel = screen.getByRole("group", { name: "Threshold events" });
    expect(panel).toHaveAttribute("id", "events");
    expect(screen.getByText("inside")).toBeInTheDocument();
  });

  it("renders a Section as a heading over its content and its actions", () => {
    render(
      <Section
        title="Saved analyses"
        subtitle="Reopen or delete"
        actions={<button type="button">Refresh</button>}
      >
        <p>list</p>
      </Section>,
    );
    expect(screen.getByRole("heading", { name: "Saved analyses" })).toBeInTheDocument();
    expect(screen.getByText("Reopen or delete")).toBeInTheDocument();
    expect(screen.getByText("list")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
  });
});
