import { LayoutDashboard, SquareChartGantt, LayoutGrid, SquarePen } from 'lucide-react'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'

const popularServices = [
  {
    icon: LayoutGrid,
    title: 'Appstore',
    subtitle: '유용한 App 및 Report를 한곳에서 확인 가능',
    category: 'App, Report',
    popular: true,
    href: '/appstore'
  },
  {
    icon: LayoutDashboard,
    title: 'ESOP Dashboard',
    subtitle: 'Engineer가 보낸 NPW 및 Sample의 진행 상황을 한눈에 확인할 수 있는 Dashboard',
    category: 'System',
    popular: true,
    href: '/ESOP_Dashboard'
  },
  {
    icon: SquareChartGantt,
    title: 'Timeline',
    subtitle: '설비 변경점 이력을 한눈에 파악할 수 있는 Timeline',
    category: 'System',
    popular: false,
    href: '/timeline'
  },
  {
    icon: SquarePen,
    title: 'VoE',
    subtitle: '자동화 업무문의 & 지원',
    category: 'VoC',
    popular: false,
    href: '/voc'
  }
]

// ------------------------------------------------------
// 🔶 재사용 가능한 UnifiedCard 컴포넌트
// ------------------------------------------------------
export const UnifiedCard = ({ children, className = '', hover = true, variant = 'default' }) => {
  const baseClasses =
    'bg-card dark:bg-card border border-border/50 rounded-2xl p-6 shadow-sm transition-all duration-300'
  const hoverClasses = hover ? 'hover:shadow-lg hover:border-primary/20 hover:-translate-y-1' : ''

  const variantClasses = {
    service: 'min-h-[160px] flex flex-col',
    stat: 'min-h-[160px] flex flex-col justify-center text-center',
    trust: 'min-h-[80px] flex flex-col justify-center p-3',
    default: ''
  }

  return (
    <div className={`${baseClasses} ${hoverClasses} ${variantClasses[variant]} ${className}`}>
      {children}
    </div>
  )
}

// ------------------------------------------------------
// 🔶 Popular Services Grid
// ------------------------------------------------------
export function PopularServicesSection() {
  return (
    <section className='py-10 -mt-15'>
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.3 }}
        className='mx-auto w-full max-w-5xl px-4 sm:px-6 lg:px-8'
      >
        <div className='grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4'>
          {popularServices.map((service, index) => (
            <Link
              to={service.href}
              key={service.title}
              className='group relative block h-full'
            >
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.4 + index * 0.1 }}
                whileHover={{
                  y: -4,
                  scale: 1.02,
                  transition: { duration: 0.2 }
                }}
                className='relative h-full cursor-pointer'
              >
                <UnifiedCard variant='service' className='relative h-full'>
                  {service.popular && (
                    <Badge className='absolute -top-2 -right-2 z-10 border border-primary/20 bg-primary/10 px-2 py-1 text-xs font-medium text-primary'>
                      Popular
                    </Badge>
                  )}

                  <div className='mb-4 flex size-12 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 transition-all duration-300 group-hover:border-primary/30 group-hover:bg-primary/15'>
                    <service.icon className='size-6 text-primary' />
                  </div>

                  <div className='flex flex-1 flex-col justify-between text-left'>
                    <div>
                      <h4 className='mb-2 text-base font-semibold leading-tight text-foreground transition-colors group-hover:text-primary'>
                        {service.title}
                      </h4>
                      <p className='mb-3 text-sm leading-relaxed text-muted-foreground'>
                        {service.subtitle}
                      </p>
                    </div>

                    <div className='text-xs font-medium text-primary/70'>{service.category}</div>
                  </div>
                </UnifiedCard>
              </motion.div>
            </Link>
          ))}
        </div>
      </motion.div>
    </section>
  )
}