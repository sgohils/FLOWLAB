import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..");

/** Every .ts/.tsx under src/, excluding this test's own helper code. */
function sourceFiles(dir = SRC): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    return /\.tsx?$/.test(entry.name) ? [full] : [];
  });
}

const REPLACEMENT = "\uFFFD";

/**
 * A U+FFFD is what a file looks like after text has been through an encoding
 * that could not represent one of its characters. It compiles, it typechecks,
 * and it ships - rendered as a black diamond in the interface, or silently
 * swallowed when it lands inside an identifier. One shipped in a button label
 * before this test existed, so the check is over the bytes rather than over the
 * rendered console output, which would have hidden it.
 */
describe("source encoding", () => {
  const files = sourceFiles();

  it("finds the files it is meant to be checking", () => {
    // A sweep that silently matched nothing would pass everything.
    expect(files.length).toBeGreaterThan(20);
  });

  it("no source file contains a U+FFFD replacement character", () => {
    const offenders = files
      .filter((file) => readFileSync(file, "utf8").includes(REPLACEMENT))
      .map((file) => file.slice(SRC.length + 1));
    expect(offenders).toEqual([]);
  });

  it("no source file is a byte-order mark or a UTF-16 artefact", () => {
    const offenders = files.filter((file) => {
      const bytes = readFileSync(file);
      return bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf;
    });
    expect(offenders.map((file) => file.slice(SRC.length + 1))).toEqual([]);
  });

  it("uses LF line endings, so the tree is not half CRLF", () => {
    const offenders = files.filter((file) => readFileSync(file, "utf8").includes("\r\n"));
    expect(offenders.map((file) => file.slice(SRC.length + 1))).toEqual([]);
  });
});
