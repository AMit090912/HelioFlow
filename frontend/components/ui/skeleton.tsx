import { cn } from "cn"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      // Visible on the page background (surface) as well as inside white cards.
      className={cn("animate-pulse rounded-md bg-ink/[0.08]", className)}
      {...props}
    />
  )
}

export { Skeleton }
