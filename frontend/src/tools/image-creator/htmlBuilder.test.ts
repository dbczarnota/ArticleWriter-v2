import { describe, it, expect } from "vitest";
import { buildHtml, escapeHtml } from "./htmlBuilder";

describe("escapeHtml", () => {
  it("escapes HTML special chars", () => {
    expect(escapeHtml('<script>alert("xss")</script>')).toBe(
      "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;"
    );
  });
});

describe("buildHtml", () => {
  it("replaces TEXT placeholders with escaped values", () => {
    const html = "<h1>{{TEXT:title}}</h1>";
    const result = buildHtml(html, { title: "Hello <world>" }, {});
    expect(result).toBe("<h1>Hello &lt;world&gt;</h1>");
  });

  it("replaces IMAGE placeholders with wrapped img tag", () => {
    const html = "<div>{{IMAGE:photo}}</div>";
    const imageStates = {
      photo: { dataUrl: "data:image/jpeg;base64,abc", panX: 12, panY: -8, scale: 1.5 },
    };
    const result = buildHtml(html, {}, imageStates);
    expect(result).toContain('src="data:image/jpeg;base64,abc"');
    expect(result).toContain('data-slot="photo"');
    expect(result).toContain('data-pan-x="12"');
    expect(result).toContain('data-pan-y="-8"');
    expect(result).toContain('data-scale="1.5"');
    expect(result).toContain("min-width:150%");
    expect(result).toContain("min-height:150%");
    expect(result).toContain("translate(calc(-50% + 12px), calc(-50% + -8px))");
  });

  it("leaves IMAGE placeholder empty when no image uploaded", () => {
    const html = "<div>{{IMAGE:photo}}</div>";
    const result = buildHtml(html, {}, {});
    expect(result).toBe("<div></div>");
  });
});
