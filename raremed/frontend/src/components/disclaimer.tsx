import { Shield } from "lucide-react";

import { cn } from "@/lib/utils";

export function Disclaimer({
  text,
  compact = false,
  className,
}: {
  text: string;
  compact?: boolean;
  className?: string;
}) {
  return (
    <p
      data-testid="disclaimer"
      className={cn(
        "flex gap-2 text-pretty text-muted-foreground",
        compact ? "items-center text-xs" : "items-start text-sm leading-6",
        className,
      )}
    >
      <Shield className={cn("shrink-0 text-copper", compact ? "size-3.5" : "mt-0.5 size-4")} aria-hidden="true" />
      <span>{text}</span>
    </p>
  );
}
