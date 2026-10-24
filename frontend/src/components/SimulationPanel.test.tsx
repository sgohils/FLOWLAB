import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Scenario } from "../types";
import { describePresets, offlinePresets, SimulationPanel } from "./SimulationPanel";

/** A scenario with every field the backend promises. */
function scenario(overrides: Partial<Scenario> = {}): Scenario {
  return {
    volume: 1,
    service_multiplier: 1,
    spread_seconds: 0,
    channels: 1,
    seed: 7,
    ...overrides,
  } as Scenario;
}


describe("describePresets", () => {
  it("uses the worded label of a preset it recognises", () => {
    const described = describePresets([
      scenario({ volume: 0.75 }),
      scenario({ service_multiplier: 1.5 }),
    ]);
    expect(described.map((preset) => preset.key)).toEqual(["lower_volume", "faster_exit"]);
    expect(described[0].label).toBe("Volume -25%");
  });

  it("passes the backend's numbers through as a patch", () => {
    const [preset] = describePresets([
      scenario({ volume: 0.75, service_multiplier: 1, spread_seconds: 0, channels: 1 }),
    ]);
    expect(preset?.patch).toEqual({
      volume: 0.75,
      serviceMultiplier: 1,
      spreadSeconds: 0,
      channels: 1,
    });
  });

  it("words an unrecognised preset from its own numbers", () => {
    const [preset] = describePresets([scenario({ volume: 1.25, spread_seconds: 60 })]);
    expect(preset?.label).toBe("volume +25%, spread +60 s");
  });

  it("joins the parts of a multi-change label the way the backend does", () => {
    // backend/simulation/scenarios.py describe(): ", ".join(parts).  A label
    // worded there and one worded here have to be the same string.
    const [preset] = describePresets([
      scenario({ volume: 1.2, service_multiplier: 1.5, spread_seconds: 60, channels: 2 }),
    ]);
    expect(preset?.label).toBe(
      "volume +20%, 1.50x exit, spread +60 s, 2 exit lanes",
    );
  });

  it("never emits a replacement character into a label", () => {
    for (const described of describePresets([
      scenario({ volume: 1.2 }),
      scenario({ service_multiplier: 0.8, channels: 2 }),
    ])) {
      expect(described.label).not.toContain("\uFFFD");
      expect(described.label.codePointAt(0)).not.toBe(0xfffd);
    }
  });

  it("labels a preset that changes nothing as Observed", () => {
    const [preset] = describePresets([scenario()]);
    expect(preset?.label).toBe("Observed");
  });

  it("returns nothing at all for no scenarios", () => {
    expect(describePresets([])).toEqual([]);
  });
});

describe("describePresets, malformed input", () => {
  /** Collected so the drop is asserted rather than merely tolerated. */
  function captureWarn() {
    const spy = vi.spyOn(console, "warn").mockImplementation(() => {});
    return spy;
  }

  it("drops a preset whose volume is not a number at all", () => {
    const warn = captureWarn();
    // A payload where the field never arrived.  Rendered, the arithmetic in
    // describe() would have formatted a value it does not have.
    const described = describePresets([
      { volume: undefined, service_multiplier: 1, spread_seconds: 0, channels: 1 } as unknown as Scenario,
    ]);
    expect(described).toEqual([]);
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it("drops a preset that carries NaN", () => {
    const warn = captureWarn();
    const described = describePresets([
      scenario({ service_multiplier: Number.NaN }),
    ]);
    expect(described).toEqual([]);
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it("drops a preset that carries Infinity", () => {
    const warn = captureWarn();
    expect(describePresets([scenario({ spread_seconds: Number.POSITIVE_INFINITY })])).toEqual([]);
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it("drops a preset whose channels is null, rather than reading it as one", () => {
    const warn = captureWarn();
    // null is falsy, so an unguarded `channels > 1` would skip it and the
    // preset would look like plain observed traffic.
    const described = describePresets([
      { volume: 1, service_multiplier: 1, spread_seconds: 0, channels: null } as unknown as Scenario,
    ]);
    expect(described).toEqual([]);
    expect(warn).toHaveBeenCalledTimes(1);
  });

  it("keeps the usable presets around a broken one", () => {
    const warn = captureWarn();
    const described = describePresets([
      scenario({ volume: 0.75 }),
      { volume: "1.5", service_multiplier: 1, spread_seconds: 0, channels: 1 } as unknown as Scenario,
      scenario({ channels: 2 }),
    ]);
    expect(described.map((preset) => preset.key)).toEqual([
      "lower_volume",
      "second_channel",
    ]);
    expect(warn).toHaveBeenCalledTimes(1);
    expect(String(warn.mock.calls[0]?.[0])).toContain("Scenario 1 dropped");
  });

  it("labels nothing as NaN", () => {
    const warn = captureWarn();
    const described = describePresets([
      scenario({ volume: 1.2 }),
      {
        volume: undefined,
        service_multiplier: 1.5,
        spread_seconds: 30,
        channels: 2,
      } as unknown as Scenario,
    ]);
    for (const preset of described) {
      expect(preset.label).not.toMatch(/NaN|undefined|Infinity/);
    }
    expect(warn).toHaveBeenCalledTimes(1);
  });
});

describe("SimulationPanel", () => {
  const base = {
    volume: 1,
    serviceMultiplier: 1,
    spreadSeconds: 0,
    channels: 1,
    onChange: vi.fn(),
    onRun: vi.fn(),
    onReset: vi.fn(),
    running: false,
    arrivalRate: 4,
    serviceTime: 6,
    presetsOffline: false,
  };

  it("renders one button per preset and applies the patch when chosen", async () => {
    const onChange = vi.fn();
    render(
      <SimulationPanel {...base} onChange={onChange} presets={offlinePresets()} />,
    );
    // One preset per experiment; the one matching the current controls is
    // marked pressed, so it is excluded from the unpressed count.
    const presets = offlinePresets();
    expect(screen.getAllByRole("button", { pressed: false }).length).toBe(presets.length - 1);
    expect(screen.getAllByRole("button", { pressed: true }).length).toBe(1);
    await userEvent.click(screen.getByText("Second exit lane").closest("button")!);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ channels: 2 }),
    );
  });

  it("marks the offline fallback, so the list is not passed off as the backend's", () => {
    render(<SimulationPanel {...base} presets={offlinePresets()} presetsOffline />);
    expect(screen.getByText("built-in presets")).toBeInTheDocument();
  });

  it("does not claim to be the backend's list when it is", () => {
    render(<SimulationPanel {...base} presets={offlinePresets()} />);
    expect(screen.queryByText("built-in presets")).not.toBeInTheDocument();
  });
});
