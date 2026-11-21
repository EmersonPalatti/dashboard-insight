import { describe, expect, it } from "vitest";
import { escapeHtml } from "./EChart";

describe("escapeHtml", () => {
  it("escapa os cinco caracteres especiais do HTML", () => {
    expect(escapeHtml(`<img src=x onerror="alert('x')">&`)).toBe(
      "&lt;img src=x onerror=&quot;alert(&#39;x&#39;)&quot;&gt;&amp;",
    );
  });

  it("mantém texto comum e acentos intactos", () => {
    expect(escapeHtml("Loja São João · 4,6%")).toBe("Loja São João · 4,6%");
    expect(escapeHtml("")).toBe("");
  });

  it("escapa o & de uma entidade pronta: o texto dos dados chega cru, nunca como HTML", () => {
    expect(escapeHtml("&amp;")).toBe("&amp;amp;");
  });
});
