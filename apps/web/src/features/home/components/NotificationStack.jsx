import { useEffect, useState } from 'react'

import { motion } from 'motion/react'

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { buildProfileImageUrl, resolveProfileAvatarId } from '@/lib/profileImage'

const NotificationStack = ({
  notifications: initialNotifications
}) => {
  const [notifications, setNotifications] = useState(initialNotifications)

  useEffect(() => {
    const interval = setInterval(() => {
      setNotifications(prevCards => {
        const newArray = [...prevCards]

        newArray.unshift(newArray.pop())

        return newArray
      })
    }, 2000)

    return () => clearInterval(interval);
  }, [])

  return (
    <div className='relative h-24.5'>
      {notifications.map((notification, index) => {
        const profileAvatarId = resolveProfileAvatarId(notification)
        const avatarSrc = buildProfileImageUrl(profileAvatarId)

        return (
          <motion.div
            key={notification.id}
            className='bg-background absolute left-1/2 flex w-full -translate-x-1/2 items-center justify-between rounded-md px-6 py-2.5 shadow-xs'
            style={{
              transformOrigin: 'top center'
            }}
            animate={{
              top: (index - 2) * -8,
              scale: 1 - index * 0.05,
              opacity: 1 - index * 0.25,
              zIndex: notifications.length - index
            }}
            transition={{
              duration: 0.4,
              ease: 'easeInOut'
            }}>
            <div className='flex items-center gap-4'>
              <Avatar className='size-15.5'>
                <AvatarImage src={avatarSrc || undefined} alt={notification.name} />
                <AvatarFallback>{notification.fallback}</AvatarFallback>
              </Avatar>

              <div className='space-y-1'>
                <p className='text-lg font-semibold'>{notification.name}</p>
                <p className='text-muted-foreground'>{notification.time}</p>
              </div>
            </div>

            <span className='text-lg font-semibold'>{notification.amount}</span>
          </motion.div>
        )
      })}
    </div>
  );
}

export default NotificationStack
