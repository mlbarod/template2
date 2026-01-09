// 리액트 임포트
import { useRef } from 'react'

import { FileInputIcon, RepeatIcon, UserIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

import NotificationStack from './NotificationStack'
import { StraightBeam } from './StraightBeam'

import { MotionPreset } from '@/components/ui/motion-preset'
import { Cursor, CursorFollow, CursorProvider } from '@/components/ui/cursor'

import { LogoVector } from "@/components/common"
import { buildProfileImageUrl, resolveProfileAvatarId } from '@/lib/profileImage'
import { cn } from '@/lib/utils'

const FeaturesSection = ({
  notifications,
  avatarData
}) => {
  const containerRef = useRef(null)
  const div1Ref = useRef(null)
  const div2Ref = useRef(null)
  const div3Ref = useRef(null)
  const div4Ref = useRef(null)
  const div5Ref = useRef(null)
  const div6Ref = useRef(null)
  const div7Ref = useRef(null)
  const div8Ref = useRef(null)
  const span1Ref = useRef(null)
  const span2Ref = useRef(null)
  const span3Ref = useRef(null)
  const span4Ref = useRef(null)
  const span5Ref = useRef(null)
  const span6Ref = useRef(null)
  const span7Ref = useRef(null)
  const span8Ref = useRef(null)
  const span9Ref = useRef(null)

  return (
    <section className='py-8 sm:py-16 lg:py-24'>
      <div className='mx-auto max-w-7xl px-4 sm:px-6 lg:px-8'>
        {/* 헤더 */}
        <div className='mb-12 space-y-4 text-center sm:mb-16 lg:mb-24'>
          <MotionPreset
            fade
            blur
            slide={{ direction: 'up', offset: 50 }}
            transition={{ duration: 0.5 }}>
            <Badge className='text-sm font-normal' variant='outline'>
              Our Features
            </Badge>
          </MotionPreset>
          <MotionPreset
            component='h2'
            className='text-2xl font-semibold md:text-3xl lg:text-4xl'
            fade
            blur
            slide={{ direction: 'up', offset: 50 }}
            delay={0.3}
            transition={{ duration: 0.5 }}>
            Offer your clients a better retainer experience, scale your agency
          </MotionPreset>
          <MotionPreset
            component='p'
            className='text-muted-foreground text-xl'
            fade
            blur
            slide={{ direction: 'up', offset: 50 }}
            delay={0.5}
            transition={{ duration: 0.5 }}>
            Using technology to make finance simpler, smarter and more rewarding.
          </MotionPreset>
        </div>

        <div
          ref={containerRef}
          className='relative isolate flex w-full flex-col items-center gap-18'>
          <MotionPreset
            fade
            blur
            delay={0.05}
            transition={{ duration: 0.5 }}
            className='bg-primary animate-heartbeat z-1 flex h-14.5 w-fit items-center gap-4 rounded-full px-3.5 text-2xl font-medium text-white shadow-2xl [--heartbeat-color:var(--primary)] lg:hidden dark:text-black'>
            <div
              className='bg-primary flex size-10 items-center justify-center rounded-full border-2 border-white dark:border-black'>
              <LogoVector className='size-16 text-white dark:text-black' />
            </div>
            Shadcn
          </MotionPreset>

          <div
            className='relative flex w-full items-center justify-center max-lg:flex-wrap max-lg:gap-6 lg:justify-between'>
            <div className='flex gap-6 lg:flex-col lg:gap-18'>
              <MotionPreset
                fade
                blur
                delay={0.05}
                transition={{ duration: 0.5 }}
                ref={div2Ref}
                className='bg-background flex h-11 w-fit items-center gap-2 rounded-md border px-2 text-lg shadow-sm'>
                <img
                  src='https://cdn.shadcnstudio.com/ss-assets/blocks/marketing/features/image-22.png'
                  alt='Stripe'
                  className='relative size-6.5 rounded-md object-cover' />
                Stripe
              </MotionPreset>
              <MotionPreset
                fade
                blur
                delay={0.05}
                transition={{ duration: 0.5 }}
                ref={div3Ref}
                className='bg-background flex h-11 w-fit items-center gap-2 rounded-md border px-2 text-lg shadow-sm'>
                <img
                  src='https://cdn.shadcnstudio.com/ss-assets/blocks/marketing/features/image-21.png'
                  alt='Filament'
                  className='relative size-6.5 rounded-md object-cover' />
                Filament
              </MotionPreset>
            </div>

            <div className='flex flex-col gap-14 max-lg:hidden'>
              <span ref={span1Ref} className='size-0.5' />
              <span ref={span2Ref} className='size-0.5' />
              <span ref={span3Ref} className='size-0.5' />
            </div>

            <MotionPreset
              fade
              blur
              delay={0.05}
              transition={{ duration: 0.5 }}
              ref={div1Ref}
              className='bg-primary animate-heartbeat z-1 flex h-14.5 w-fit items-center gap-4 rounded-full px-3.5 text-2xl font-medium text-white shadow-2xl [--heartbeat-color:var(--primary)] max-lg:hidden dark:text-black'>
              <div
                className='bg-primary flex size-10 items-center justify-center rounded-full border-2 border-white dark:border-black'>
                <LogoVector className='size-16 text-white dark:text-black' />
              </div>
              Shadcn
            </MotionPreset>

            <div className='flex flex-col gap-14 max-lg:hidden'>
              <span ref={span4Ref} className='size-0.5' />
              <span ref={span5Ref} className='size-0.5' />
              <span ref={span6Ref} className='size-0.5' />
            </div>
            <div className='flex gap-6 lg:flex-col lg:gap-18'>
              <MotionPreset
                fade
                blur
                delay={0.05}
                transition={{ duration: 0.5 }}
                ref={div4Ref}
                className='bg-background flex h-11 w-fit items-center gap-2 rounded-md border px-2 text-lg shadow-sm'>
                <img
                  src='https://cdn.shadcnstudio.com/ss-assets/blocks/marketing/features/image-19.png'
                  alt='Supabase'
                  className='relative size-6.5 rounded-md object-cover' />
                Supabase
              </MotionPreset>

              <MotionPreset
                fade
                blur
                delay={0.05}
                transition={{ duration: 0.5 }}
                ref={div5Ref}
                className='bg-background flex h-11 w-fit items-center gap-2 rounded-md border px-2 text-lg shadow-sm'>
                <img
                  src='https://cdn.shadcnstudio.com/ss-assets/blocks/marketing/features/image-20.png'
                  alt='User'
                  className='relative size-6.5 rounded-md object-cover' />
                UserAuth
              </MotionPreset>
            </div>
          </div>
          <div className='grid gap-5 md:grid-cols-2 lg:grid-cols-3'>
            <MotionPreset
              fade
              blur
              delay={0.1}
              transition={{ duration: 0.9 }}
              className='relative flex flex-col items-center gap-18'>
              <span ref={span7Ref} className='size-0.5 max-lg:hidden' />
              <div ref={div6Ref} className='bg-card overflow-hidden rounded-xl border'>
                <div className='px-6 pt-6 text-center'>
                  <div className='flex items-center justify-center gap-1.5 text-lg font-medium'>
                    <RepeatIcon className='size-4.5 shrink-0' />
                    Usage Transparency
                  </div>
                  <p className='text-muted-foreground mt-1.5'>
                    Protect your sensitive information with advanced security measures.
                  </p>
                </div>
                <div className='relative mt-2.5 sm:pl-6'>
                  <div
                    className='bg-primary/10 flex h-63 w-full items-center justify-center sm:rounded-tl-md'>
                    <img
                      src='https://cdn.shadcnstudio.com/ss-assets/blocks/marketing/features/image-16.png'
                      alt='UsageTransparency'
                      className='relative w-full max-w-80 rounded-md object-cover transition-transform duration-300 hover:scale-110' />
                  </div>
                </div>
              </div>
            </MotionPreset>
            <MotionPreset
              fade
              blur
              delay={0.12}
              transition={{ duration: 0.9 }}
              className='relative flex flex-col items-center gap-18'>
              <span ref={span8Ref} className='size-0.5 max-lg:hidden' />
              <div ref={div7Ref} className='bg-card overflow-hidden rounded-xl border'>
                <div className='px-6 pt-6 text-center'>
                  <div className='flex items-center justify-center gap-1.5 text-lg font-medium'>
                    <UserIcon className='size-4.5 shrink-0' />
                    Client-facing Portal
                  </div>
                  <p className='text-muted-foreground mt-1.5'>
                    Protect your sensitive information with advanced security measures.
                  </p>
                </div>
                <div className='mt-2.5 sm:pl-6'>
                  <div
                    className='flex h-63 w-full flex-col justify-center bg-sky-600/10 px-4 sm:rounded-tl-md dark:bg-sky-400/40'>
                    <NotificationStack notifications={notifications} />
                  </div>
                </div>
              </div>
            </MotionPreset>
            <MotionPreset
              fade
              blur
              delay={0.15}
              transition={{ duration: 0.9 }}
              className='relative flex flex-col items-center gap-18'>
              <span ref={span9Ref} className='size-0.5 max-lg:hidden' />
              <div ref={div8Ref} className='bg-card overflow-hidden rounded-xl border'>
                <div className='px-6 pt-6 text-center'>
                  <div className='flex items-center justify-center gap-1.5 text-lg font-medium'>
                    <FileInputIcon className='size-4.5 shrink-0' />
                    Task Colllbration
                  </div>
                  <p className='text-muted-foreground mt-1.5'>
                    Protect your sensitive information with advanced security measures.
                  </p>
                </div>
                <div className='relative mt-2.5 sm:pl-6'>
                  <div
                    className='flex h-63 w-full items-center justify-center bg-green-600/10 sm:rounded-tl-md dark:bg-green-400/40'>
                    <div className='flex min-h-20 flex-1 items-center justify-center -space-x-4'>
                      {avatarData.map(item => {
                        const profileAvatarId = resolveProfileAvatarId(item)
                        const avatarSrc = buildProfileImageUrl(profileAvatarId)

                        return (
                          <div key={item.name}>
                            <Avatar className={cn('ring-ring ring-2', item.size)}>
                              <AvatarImage src={avatarSrc || undefined} alt={item.name} />
                              <AvatarFallback>{item.fallback}</AvatarFallback>
                            </Avatar>
                            <CursorProvider>
                              <Cursor>
                                <svg
                                  className='size-6 text-sky-600 dark:text-sky-400'
                                  xmlns='http://www.w3.org/2000/svg'
                                  viewBox='0 0 40 40'>
                                  <path
                                    fill='currentColor'
                                    d='M1.8 4.4 7 36.2c.3 1.8 2.6 2.3 3.6.8l3.9-5.7c1.7-2.5 4.5-4.1 7.5-4.3l6.9-.5c1.8-.1 2.5-2.4 1.1-3.5L5 2.5c-1.4-1.1-3.5 0-3.3 1.9Z' />
                                </svg>
                              </Cursor>
                              <CursorFollow>
                                <div
                                  className='w-fit rounded-lg bg-sky-600 px-2 py-1 text-sm text-nowrap text-white shadow-lg dark:bg-sky-400'>
                                  {item.name}
                                </div>
                              </CursorFollow>
                            </CursorProvider>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
              </div>
            </MotionPreset>
          </div>
          {/* 상단 */}

          <StraightBeam
            containerRef={containerRef}
            fromRef={div1Ref}
            toRef={span2Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden'
            reverse />

          <StraightBeam
            containerRef={containerRef}
            fromRef={div1Ref}
            toRef={span5Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden' />

          <StraightBeam
            containerRef={containerRef}
            fromRef={span2Ref}
            toRef={span1Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden'
            reverse />

          <StraightBeam
            containerRef={containerRef}
            fromRef={span1Ref}
            toRef={div2Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden'
            reverse />

          <StraightBeam
            containerRef={containerRef}
            fromRef={span2Ref}
            toRef={span3Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden'
            reverse />

          <StraightBeam
            containerRef={containerRef}
            fromRef={span3Ref}
            toRef={div3Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden'
            reverse />

          <StraightBeam
            containerRef={containerRef}
            fromRef={span5Ref}
            toRef={span4Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden' />

          <StraightBeam
            containerRef={containerRef}
            fromRef={span4Ref}
            toRef={div4Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden' />

          <StraightBeam
            containerRef={containerRef}
            fromRef={span5Ref}
            toRef={span6Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden' />

          <StraightBeam
            containerRef={containerRef}
            fromRef={span6Ref}
            toRef={div5Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden' />

          {/* 하단 빔 */}
          <StraightBeam
            containerRef={containerRef}
            fromRef={div1Ref}
            toRef={span8Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden'
            startXOffset={5}
            startYOffset={20} />
          <StraightBeam
            containerRef={containerRef}
            fromRef={span8Ref}
            toRef={span7Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            reverse
            className='-z-1 max-lg:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={span8Ref}
            toRef={span9Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={span8Ref}
            toRef={div7Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={span7Ref}
            toRef={div6Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            reverse
            className='-z-1 max-lg:hidden' />
          <StraightBeam
            containerRef={containerRef}
            fromRef={span9Ref}
            toRef={div8Ref}
            gradientStartColor='var(--primary)'
            duration={4.5}
            className='-z-1 max-lg:hidden' />
        </div>
      </div>
    </section>
  );
}

export default FeaturesSection
