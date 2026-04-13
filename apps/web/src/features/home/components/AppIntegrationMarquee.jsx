import { Marquee } from '@/components/ui/marquee'

import IntegrationCard from './IntegrationCard'
import { IoIosApps } from "react-icons/io";

const AppIntegrationMarquee = ({
  apps
}) => {
  const midpoint = Math.ceil(apps.length / 2)
  const topApps = apps.slice(0, midpoint)
  const bottomApps = apps.slice(midpoint)

  const baseDuration = 50
  const topCount = Math.max(topApps.length, 1)
  const getDurationForCount = (count) => baseDuration * (count / topCount)

  return (
    <section className='py-8 sm:py-12 lg:py-12'>
      <div className='mx-auto max-w-7xl px-4 sm:px-6 lg:px-8'>
        {/* Header */}
        <div className='text-center mb-12 space-y-4 sm:mb-8 lg:mb-8'>
          <div className='flex items-center justify-center gap-2'>

            <IoIosApps className='size-10 text-primary' />
            <h2 className='text-xl font-semibold md:text-3xl lg:text-4xl'>MES <span className="shimmer-text">Applications</span> Link</h2>

          </div>
          <p className='text-muted-foreground text-md'> 필요한 모든 Applications를 한 곳에서 쉽게 접속 하세요</p>

        </div>
      </div>
      {/* Marquee */}
      <div className='w-full overflow-hidden'>
        <Marquee pauseOnHover duration={baseDuration} gap={1.5}>
          {topApps.map((app, index) => (
            <IntegrationCard key={index} app={app} />
          ))}
        </Marquee>
      </div>
      <div className='w-full overflow-hidden'>
        <Marquee pauseOnHover duration={getDurationForCount(bottomApps.length)} gap={1.5} reverse>
          {bottomApps.map((app, index) => (
            <IntegrationCard key={index} app={app} />
          ))}
        </Marquee>
      </div>
    </section>
  );
}

export default AppIntegrationMarquee
