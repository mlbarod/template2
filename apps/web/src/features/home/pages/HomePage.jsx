import HeroSection from "../components/HeroSection"
import AppIntegrationMarquee from "../components/AppIntegrationMarquee"
import { PopularServicesSection } from "../components/PopularSection"
import { marqueeApps } from "../utils/constants"

const HomePage = () => {
  return (
    <>
      <HeroSection />
      <PopularServicesSection />
      <AppIntegrationMarquee apps={marqueeApps} />
    </>
  )
}

export default HomePage
