import HeroSection from "../components/HeroSection"
import AppIntegrationMarquee from "../components/AppIntegrationMarquee"
import Team from "../components/Team"
import { PopularServicesSection } from "../components/PopularSection"
import { marqueeApps, teamMembers } from "../utils/constants"

const DEFAULT_HERO_ACTIONS = [
  { label: "대시보드로 이동", href: "/esop_dashboard" },
  { label: "Appstore 둘러보기", href: "/appstore", variant: "outline" },
]

const HomePage = ({ heroActions = DEFAULT_HERO_ACTIONS }) => {
  return (
    <>
      <HeroSection actions={heroActions} />
      <PopularServicesSection />
      {/* <Team teamMembers={teamMembers} /> */}
      <AppIntegrationMarquee apps={marqueeApps} />
    </>
  )
}

export default HomePage
