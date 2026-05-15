import { describe, it, expect } from "vitest";
import { parsePlaceholders } from "./parsePlaceholders";

describe("parsePlaceholders", () => {
  it("parses TEXT and IMAGE placeholders", () => {
    const html = "<h1>{{TEXT:nagłówek}}</h1><div>{{IMAGE:tło}}</div>";
    expect(parsePlaceholders(html)).toEqual([
      { type: "TEXT", label: "nagłówek" },
      { type: "IMAGE", label: "tło" },
    ]);
  });

  it("deduplicates repeated placeholders", () => {
    const html = "{{TEXT:title}} and {{TEXT:title}} again";
    expect(parsePlaceholders(html)).toHaveLength(1);
  });

  it("returns empty array for template with no placeholders", () => {
    expect(parsePlaceholders("<h1>Static</h1>")).toEqual([]);
  });

  it("preserves order of first occurrence", () => {
    const html = "{{IMAGE:photo}}{{TEXT:caption}}";
    const result = parsePlaceholders(html);
    expect(result[0].type).toBe("IMAGE");
    expect(result[1].type).toBe("TEXT");
  });
});
