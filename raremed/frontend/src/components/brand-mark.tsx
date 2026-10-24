import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-8", className)} aria-hidden="true">
      <rect x="1" y="1" width="30" height="30" rx="8" className="fill-primary/10" />
      <circle cx="10" cy="16" r="2" className="fill-primary" />
      <circle cx="16" cy="9" r="2" className="fill-primary" />
      <circle cx="23" cy="16" r="2" className="fill-copper" />
      <circle cx="16" cy="23" r="2" className="fill-primary" />
      <path
        d="M10 16 L16 9 L23 16 L16 23 Z"
        className="stroke-primary"
        fill="none"
        strokeWidth="1.2"
      />
    </svg>
  );
}
