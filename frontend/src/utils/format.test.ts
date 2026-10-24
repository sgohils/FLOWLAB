import { describe, expect, it } from "vitest";
import {
  deltaTone,
  formatBytes,
  formatClassName,
  formatFixed,
  formatNumber,
  formatPercent,
  formatSeconds,
  formatSigned,
  formatTimecode,
  formatWithUnit,
  vehicleLabel,
} from "./format";

describe("formatNumber", () => {
  it("reads a missing measurement as an em dash, never as zero", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
    expect(formatNumber(Number.NaN)).toBe("—");
  });

  it("prints an integer without a decimal point", () => {
    expect(formatNumber(0)).toBe("0");
    expect(formatNumber(42)).toBe("42");
    expect(formatNumber(-7)).toBe("-7");
  });

  it("rounds a fraction to the requested digits", () => {
    expect(formatNumber(12.34)).toBe("12.3");
    expect(formatNumber(12.34, 2)).toBe("12.34");
    expect(formatNumber(12.345, 2)).toBe("12.35");
  });

  it("keeps zero as a measurement rather than treating it as missing", () => {
    expect(formatNumber(0, 2)).toBe("0");
    expect(formatNumber(0.004, 2)).toBe("0.00");
  });
});

describe("formatWithUnit and formatFixed", () => {
  it("appends a unit with a space, and omits it when the value is missing", () => {
    expect(formatWithUnit(12.34, "s")).toBe("12.3 s");
    expect(formatWithUnit(1, "/min")).toBe("1 /min");
    expect(formatWithUnit(null, "s")).toBe("—");
    expect(formatWithUnit(undefined, "vehicles")).toBe("—");
  });

  it("keeps trailing zeros so a column of numbers stays aligned", () => {
    expect(formatFixed(0.5, 2)).toBe("0.50");
    expect(formatFixed(1, 2)).toBe("1.00");
    expect(formatFixed(0, 2)).toBe("0.00");
    expect(formatFixed(null, 2)).toBe("—");
  });
});

describe("formatPercent and formatSigned", () => {
  it("scales a fraction of one to a percentage", () => {
    expect(formatPercent(0.157)).toBe("15.7%");
    expect(formatPercent(0.5, 0)).toBe("50%");
    expect(formatPercent(1)).toBe("100%");
    expect(formatPercent(0)).toBe("0%");
    expect(formatPercent(null)).toBe("—");
  });

  it("signs a change against a baseline, and leaves zero unsigned", () => {
    expect(formatSigned(2.4)).toBe("+2.4");
    expect(formatSigned(-1)).toBe("−1");
    expect(formatSigned(0)).toBe("0");
    expect(formatSigned(null)).toBe("—");
  });

  it("puts a suffix outside the number", () => {
    expect(formatSigned(25, 0, "%")).toBe("+25%");
    expect(formatSigned(-50, 0, "%")).toBe("−50%");
  });
});

describe("formatSeconds", () => {
  it("keeps a short duration in seconds and reads a missing one as unknown", () => {
    expect(formatSeconds(0)).toBe("0.0 s");
    expect(formatSeconds(12.34)).toBe("12.3 s");
    expect(formatSeconds(59.9)).toBe("59.9 s");
    expect(formatSeconds(null)).toBe("—");
  });

  it("switches to minutes at sixty seconds", () => {
    expect(formatSeconds(60)).toBe("1m 0s");
    expect(formatSeconds(125.4)).toBe("2m 5s");
  });
});

describe("formatTimecode", () => {
  it("pads minutes and seconds, and floors a fractional second", () => {
    expect(formatTimecode(0)).toBe("00:00");
    expect(formatTimecode(65)).toBe("01:05");
    expect(formatTimecode(599)).toBe("09:59");
    expect(formatTimecode(65.9)).toBe("01:05");
  });

  it("clamps a negative time and shows a placeholder for a missing one", () => {
    expect(formatTimecode(-4)).toBe("00:00");
    expect(formatTimecode(null)).toBe("--:--");
    expect(formatTimecode(undefined)).toBe("--:--");
  });
});

describe("formatBytes", () => {
  it("reads an unknown size as an em dash rather than 0 KB", () => {
    expect(formatBytes(0)).toBe("—");
    expect(formatBytes(null)).toBe("—");
  });

  it("picks the unit from the magnitude", () => {
    expect(formatBytes(1024)).toBe("1 KB");
    expect(formatBytes(500 * 1024)).toBe("500 KB");
    expect(formatBytes(2.5 * 1024 * 1024)).toBe("2.5 MB");
  });
});

describe("formatClassName and vehicleLabel", () => {
  it("capitalises the first letter only", () => {
    expect(formatClassName("car")).toBe("Car");
    expect(formatClassName("motorcycle")).toBe("Motorcycle");
    expect(formatClassName("")).toBe("");
  });

  it("pads a vehicle id to three digits", () => {
    expect(vehicleLabel(1)).toBe("Vehicle 001");
    expect(vehicleLabel(42)).toBe("Vehicle 042");
    expect(vehicleLabel(1234)).toBe("Vehicle 1234");
  });
});

describe("deltaTone", () => {
  it("reads a falling queue as good and a rising one as bad", () => {
    expect(deltaTone(-1.2, true)).toBe("good");
    expect(deltaTone(1.2, true)).toBe("bad");
  });

  it("reads a rising throughput as good and a falling one as bad", () => {
    expect(deltaTone(1.2, false)).toBe("good");
    expect(deltaTone(-1.2, false)).toBe("bad");
  });

  it("calls a change inside a tenth of a percent flat", () => {
    expect(deltaTone(0, true)).toBe("flat");
    expect(deltaTone(0.005, false)).toBe("flat");
    expect(deltaTone(-0.009, true)).toBe("flat");
    expect(deltaTone(0.01, true)).toBe("bad");
    expect(deltaTone(0.01, false)).toBe("good");
  });
});
