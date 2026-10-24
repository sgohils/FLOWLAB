import { describe, expect, it } from "vitest";
import { hasQueueRegion } from "./index";
import type { Regions } from "./index";

/** Only the fields the guard reads; the rest of a Regions payload is noise here. */
function regions(queue: unknown): Regions {
  return { queue } as unknown as Regions;
}

describe("hasQueueRegion", () => {
  it("accepts a polygon of three or more corners", () => {
    expect(hasQueueRegion(regions([[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]]))).toBe(true);
    expect(
      hasQueueRegion(regions([[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]])),
    ).toBe(true);
  });

  it("rejects an unfinished polygon of one or two corners", () => {
    expect(hasQueueRegion(regions([]))).toBe(false);
    expect(hasQueueRegion(regions([[0.1, 0.1]]))).toBe(false);
    expect(hasQueueRegion(regions([[0.1, 0.1], [0.5, 0.5]]))).toBe(false);
  });

  it("rejects a missing analysis outright", () => {
    expect(hasQueueRegion(null)).toBe(false);
    expect(hasQueueRegion(undefined)).toBe(false);
  });

  it("rejects a payload whose queue is not a list of points", () => {
    expect(hasQueueRegion(regions(null))).toBe(false);
    expect(hasQueueRegion(regions("drawn"))).toBe(false);
  });
});
