import * as React from "react"
import { cn } from "../../lib/utils"

const badgeVariants = {
  default: "border-transparent bg-primary text-primary-foreground",
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  warning: "border-yellow-500/30 bg-yellow-500/10 text-yellow-400",
  destructive: "border-red-500/30 bg-red-500/10 text-red-400",
  muted: "border-gray-500/30 bg-gray-500/10 text-gray-400",
  info: "border-blue-500/30 bg-blue-500/10 text-blue-400",
}

function Badge({ className, variant = "default", ...props }) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
        badgeVariants[variant] || badgeVariants.default,
        className
      )}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
