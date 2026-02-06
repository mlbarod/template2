import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Error04Illustration } from "@/components/common"

function ErrorPage04({
  title = "Page not found",
  description = "We couldn't find the page you are looking for.",
  actionLabel = "Back to home page",
  homeHref = "/",
}) {
  return (
    <div className="h-screen flex flex-col bg-background">
      <header className="h-14 shrink-0 border-b bg-background" />
      <main className="flex-1 min-h-0 overflow-hidden">
        <div className="flex h-full min-h-0 flex-col items-center justify-center gap-12 overflow-y-auto px-8 pt-6 pb-8 sm:pt-14 sm:pb-16 lg:justify-between lg:pt-20 lg:pb-24">
          <Error04Illustration aria-hidden="true" className="h-[clamp(300px,50vh,600px)]" />
          <div className="text-center">
            <h1 className="mb-1.5 text-2xl font-semibold">{title}</h1>
            <p className="mb-5 text-muted-foreground">{description}</p>
            <Button size="lg" className="rounded-lg text-base" asChild>
              <Link to={homeHref}>{actionLabel}</Link>
            </Button>
          </div>
        </div>
      </main>
    </div>
  )
}

export default ErrorPage04
