import { useRef } from 'react'
import {
  BotMessageSquareIcon,
  CodeXmlIcon,
  DatabaseIcon,
  ChartSpline,
  Cloud,
  Cpu,
  Puzzle,
  ThumbsUp,
  HeartHandshake,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { LogoVector } from "@/components/common"
import { useTheme } from '@/lib/theme'

import { StraightBeam } from './StraightBeam'

const HeroSection = () => {
  const { theme = 'system', systemTheme } = useTheme()
  const containerRef = useRef(null)
  const iconRef1 = useRef(null)
  const iconRef2 = useRef(null)
  const iconRef3 = useRef(null)
  const iconRef4 = useRef(null)
  const iconRef5 = useRef(null)
  const iconRef6 = useRef(null)
  const iconRef7 = useRef(null)
  const spanRef1 = useRef(null)
  const spanRef2 = useRef(null)
  const spanRef3 = useRef(null)
  const spanRef4 = useRef(null)
  const spanRef5 = useRef(null)
  const spanRef6 = useRef(null)
  const spanRef7 = useRef(null)
  const spanRef8 = useRef(null)
  const resolvedTheme = theme === 'system' ? systemTheme : theme
  const videoSrc = resolvedTheme === 'dark' ? 'assets/video2.mp4' : 'assets/video.mp4'

  return (
    <section className='w-full overflow-hidden py-12 sm:py-8 lg:py-8'>
      <div
        className='mx-auto flex max-w-7xl flex-col items-center gap-8 px-4 sm:gap-16 sm:px-6 lg:gap-12 lg:px-8'>
        {/* Hero Content */}
        <div className='flex flex-col items-center gap-5 text-center'>
          <Badge variant='outline' className='text-sm font-normal'>
            메모리Etch기술팀
          </Badge>

          <h1 className="text-2xl font-semibold sm:text-3xl lg:text-6xl lg:font-bold">
            <span>Etch </span>
            <span className="shimmer-text">AI Transformation </span>
            <span> Portal</span>
          </h1>


          <p className='text-muted-foreground max-w-4xl text-md'>
            데이터 연결과 업무 자동화를 통해{' '}
            <br className='max-lg:hidden' /> AI 기반의 빠르고 스마트한 Workflow을 제공합니다.
          </p>

        </div>
        <div ref={containerRef} className='relative flex w-full flex-col items-center'>
          <div className='flex w-full max-w-4xl items-start justify-between max-md:hidden h-18'>
            <div className='flex items-center gap-30'>
              <div
                ref={iconRef1}
                className='bg-background relative z-10 flex size-12 items-center justify-center rounded-xl border-[1.5px] shadow-md lg:size-15'>
                <CodeXmlIcon className='size-7 stroke-1 lg:size-10' />
              </div>
              <span ref={spanRef1} className='size-0.5 max-md:hidden'></span>
              <div className="flex flex-col items-center gap-4 text-xl font-semibold text-foreground">
                <div className="flex items-center pl-7 gap-10 text-lg font-semibold">

                  {/* 사람존중 */}
                  <div className="flex flex-col items-center gap-1">
                    <HeartHandshake className="w-6 h-6" style={{ color: "var(--primary)" }} />
                    <span className='text-sm'>사람존중</span>
                  </div>

                  {/* 다름의인정 */}
                  <div className="flex flex-col items-center gap-1">
                    <Puzzle className="w-6 h-6" style={{ color: "var(--primary)" }} />
                    <span className='text-sm'>다름의인정</span>
                  </div>

                  {/* Value Up */}
                  <div className="flex flex-col items-center gap-1">
                    <ThumbsUp className="w-6 h-6" style={{ color: "var(--primary)" }} />
                    <span className='text-sm'>Value Up</span>
                  </div>

                </div>
              </div>
            </div>
            <div className='flex items-center gap-30'>
              <span ref={spanRef2} className='size-0.5 max-md:hidden'></span>
              <div
                ref={iconRef2}
                className='bg-background relative z-10 flex size-12 items-center justify-center rounded-xl border-[1.5px] shadow-md lg:size-15'>
                <BotMessageSquareIcon className='size-7 stroke-1 lg:size-8' />
              </div>
            </div>
          </div>
          <div className='flex w-full items-center justify-between py-2.5'>
            <div
              ref={iconRef3}
              className='bg-background relative z-10 flex size-15 shrink-0 items-center justify-center rounded-xl border-[1.5px] shadow-xl md:size-18 lg:size-23'>
              <DatabaseIcon className='size-8 stroke-1 md:size-10 lg:size-13' />
            </div>
            <div
              className='flex items-center justify-between md:w-full md:max-w-70 lg:max-w-100'>
              <div className='flex w-full max-w-20 justify-between max-md:hidden'>
                <span ref={spanRef3} className='size-0.5'></span>
                <span ref={spanRef4} className='size-0.5'></span>
              </div>
              <div
                ref={iconRef4}
                className='bg-background relative z-20 flex items-center justify-center rounded-xl border p-2'>
                <div className='bg-secondary relative flex h-50 w-50 items-center justify-center overflow-hidden rounded-xl border-[1.5px] shadow-xl'>
                  <video
                    className='aspect-video h-full w-full object-cover'
                    src={videoSrc}
                    autoPlay
                    loop
                    muted
                    playsInline
                  />
                </div>
              </div>
              <div className='flex w-full max-w-20 justify-between max-md:hidden'>
                <span ref={spanRef5} className='size-0.5'></span>
                <span ref={spanRef6} className='size-0.5'></span>
              </div>
            </div>
            <div
              ref={iconRef5}
              className='bg-background relative z-10 flex size-15 shrink-0 items-center justify-center rounded-xl border-[1.5px] shadow-xl md:size-18 lg:size-23'>
              <ChartSpline className='size-8 stroke-1 md:size-10 lg:size-13' />
            </div>
          </div>
          <div
            className='flex w-full max-w-4xl items-center justify-between max-md:hidden h-18'>
            <div className='flex items-center gap-30'>
              <div
                ref={iconRef6}
                className='bg-background relative z-10 flex size-12 items-center justify-center rounded-xl border-[1.5px] shadow-md lg:size-15'>
                <Cloud className='size-6 stroke-1 lg:size-8' />
              </div>
              <span ref={spanRef7} className='size-0.5 max-md:hidden'></span>
            </div>


            <div className='flex items-center gap-30'>
              <span ref={spanRef8} className='size-0.5 max-md:hidden'></span>
              <div
                ref={iconRef7}
                className='bg-background relative z-10 flex size-12 items-center justify-center rounded-xl border-[1.5px] shadow-md lg:size-15'>
                <Cpu className='size-7 stroke-1 lg:size-11' />
              </div>
            </div>
          </div>

          <StraightBeam
            containerRef={containerRef}
            fromRef={iconRef1}
            toRef={spanRef1}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={spanRef1}
            toRef={spanRef3}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={iconRef2}
            toRef={spanRef2}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={spanRef2}
            toRef={spanRef6}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={iconRef6}
            toRef={spanRef7}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={spanRef7}
            toRef={spanRef4}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={iconRef7}
            toRef={spanRef8}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={spanRef8}
            toRef={spanRef5}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={iconRef3}
            toRef={spanRef3}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={spanRef3}
            toRef={spanRef4}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={spanRef4}
            toRef={iconRef4}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />

          <StraightBeam
            containerRef={containerRef}
            fromRef={iconRef4}
            toRef={spanRef5}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={spanRef5}
            toRef={spanRef6}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={spanRef6}
            toRef={iconRef5}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='max-md:hidden' />

          {/* Smaller screen */}

          <StraightBeam
            containerRef={containerRef}
            fromRef={iconRef3}
            toRef={iconRef4}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='md:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={iconRef4}
            toRef={iconRef5}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='md:hidden' />
        </div>
      </div>
    </section>
  );
}

export default HeroSection
