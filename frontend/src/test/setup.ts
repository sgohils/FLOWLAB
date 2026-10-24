/**
 * Test-wide setup.  Kept to one file so a test file reads as the test, not as
 * scaffolding: jest-dom's matchers are the only thing added here.
 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
