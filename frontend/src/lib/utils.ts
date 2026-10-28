import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// Teach tailwind-merge the design-system type scale (DESIGN.md §3). Without it,
// "text-body" is mistaken for a colour and silently removes e.g. "text-accent-contrast".
const twMerge = extendTailwindMerge({
  extend: {
    theme: { text: ["caption", "small", "body", "body-lg", "title-sm", "title", "display"] },
  },
});

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Join hard-wrapped lines of corpus text while keeping paragraph breaks. */
export function unwrapLines(text: string): string {
  return text.replace(/\r\n/g, "\n").replace(/([^\n])\n(?!\n)/g, "$1 ");
}
