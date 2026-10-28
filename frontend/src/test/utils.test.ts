import { describe, expect, it } from "vitest";
import { cn, unwrapLines } from "@/lib/utils";

describe("cn", () => {
  it("keeps the text colour when combined with a design-system font size", () => {
    expect(cn("text-accent-contrast", "text-body")).toBe("text-accent-contrast text-body");
    expect(cn("text-small", "text-body")).toBe("text-body"); // two sizes still merge
  });
});

describe("unwrapLines", () => {
  it("joins hard-wrapped lines but keeps paragraphs", () => {
    expect(unwrapLines("a line\ncontinues\n\nnext para")).toBe("a line continues\n\nnext para");
  });
});
