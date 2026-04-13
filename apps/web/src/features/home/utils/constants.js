import {
  BookOpenIcon,
  LayoutGridIcon,
  MessageSquareIcon
} from 'lucide-react'

export const navigationItems = [
  {
    title: 'Apps',
    icon: LayoutGridIcon,
    items: [
      { title: 'Appstore', href: '/appstore' },
      { title: 'ESOP Dashboard', href: '/esop_dashboard' },
      { title: 'Timeline', href: '/timeline' },
      { title: '메일함', href: '/emails/inbox' },
    ]
  },
  {
    title: 'About Us',
    icon: BookOpenIcon,
    items: [
      { title: 'Team', href: '/teamstaff' },
      { title: 'Etch MOSAIC', href: 'https://mosaic.sec.samsung.net/collaboration/workspace/6514141', external: true },
      { title: 'Etch Confluence', href: 'https://confluence.samsungds.net/spaces/ETCH/overview', external: true },
    ]
  },
  {
    title: 'Contacts',
    icon: MessageSquareIcon,
    items: [
      { title: 'VoE', href: '/voc' },
    ]
  }
]


export const teamMembers = [
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-1.png',
    alt: 'Phillip Rothman',
    name: 'Phillip Rothman',
    role: 'Founder & CEO',
    link: 'mysingleim://ids=phillip-rothman',
    bgColor: 'bg-sky-600/10 dark:bg-sky-600/10',
    avatarBg: 'bg-sky-600/40 dark:bg-sky-600/40',
    socialLinkColor: 'group-hover:text-sky-600 dark:group-hover:text-sky-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-2.png',
    alt: 'James Kenter',
    name: 'James Kenter',
    role: 'Engineering Manager',
    link: 'mysingleim://ids=james-kenter',
    bgColor: 'bg-primary/10',
    avatarBg: 'bg-primary/40',
    socialLinkColor: 'group-hover:text-primary',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-3.png',
    alt: 'Alena Lubin',
    name: 'Alena Lubin',
    role: 'Frontend Developer',
    link: 'mysingleim://ids=alena-lubin',
    bgColor: 'bg-green-600/10 dark:bg-green-600/10',
    avatarBg: 'bg-green-600/40 dark:bg-green-600/40',
    socialLinkColor: 'group-hover:text-green-600 dark:group-hover:text-green-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-4.png',
    alt: 'Cristofer Kenter',
    name: 'Cristofer Kenter',
    role: 'Product Designer',
    link: 'mysingleim://ids=cristofer-kenter',
    bgColor: 'bg-destructive/10',
    avatarBg: 'bg-destructive/40',
    socialLinkColor: 'group-hover:text-destructive',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-5.png',
    alt: 'Minji Choi',
    name: 'Minji Choi',
    role: 'Data Strategist',
    link: 'mysingleim://ids=minji-choi',
    bgColor: 'bg-amber-500/10 dark:bg-amber-500/15',
    avatarBg: 'bg-amber-500/40 dark:bg-amber-500/40',
    socialLinkColor: 'group-hover:text-amber-500 dark:group-hover:text-amber-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-6.png',
    alt: 'Lila Gomez',
    name: 'Lila Gomez',
    role: 'Product Marketing Lead',
    link: 'mysingleim://ids=lila-gomez',
    bgColor: 'bg-indigo-500/10 dark:bg-indigo-500/15',
    avatarBg: 'bg-indigo-500/40 dark:bg-indigo-500/40',
    socialLinkColor: 'group-hover:text-indigo-500 dark:group-hover:text-indigo-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-7.png',
    alt: 'Samuel Wright',
    name: 'Samuel Wright',
    role: 'Customer Success Lead',
    link: 'mysingleim://ids=samuel-wright',
    bgColor: 'bg-sky-600/10 dark:bg-sky-600/10',
    avatarBg: 'bg-sky-600/40 dark:bg-sky-600/40',
    socialLinkColor: 'group-hover:text-sky-600 dark:group-hover:text-sky-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-8.png',
    alt: 'Priya Nair',
    name: 'Priya Nair',
    role: 'Data Scientist',
    link: 'mysingleim://ids=priya-nair',
    bgColor: 'bg-green-600/10 dark:bg-green-600/10',
    avatarBg: 'bg-green-600/40 dark:bg-green-600/40',
    socialLinkColor: 'group-hover:text-green-600 dark:group-hover:text-green-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-9.png',
    alt: 'Ethan Moore',
    name: 'Ethan Moore',
    role: 'Solutions Architect',
    link: 'mysingleim://ids=ethan-moore',
    bgColor: 'bg-indigo-500/10 dark:bg-indigo-500/15',
    avatarBg: 'bg-indigo-500/40 dark:bg-indigo-500/40',
    socialLinkColor: 'group-hover:text-indigo-500 dark:group-hover:text-indigo-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-10.png',
    alt: 'Hana Suzuki',
    name: 'Hana Suzuki',
    role: 'Backend Engineer',
    link: 'mysingleim://ids=hana-suzuki',
    bgColor: 'bg-primary/10',
    avatarBg: 'bg-primary/40',
    socialLinkColor: 'group-hover:text-primary',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-11.png',
    alt: 'Marco Silva',
    name: 'Marco Silva',
    role: 'Mobile Engineer',
    link: 'mysingleim://ids=marco-silva',
    bgColor: 'bg-destructive/10',
    avatarBg: 'bg-destructive/40',
    socialLinkColor: 'group-hover:text-destructive',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-12.png',
    alt: 'Ava Bennett',
    name: 'Ava Bennett',
    role: 'People Operations Manager',
    link: 'mysingleim://ids=ava-bennett',
    bgColor: 'bg-amber-500/10 dark:bg-amber-500/15',
    avatarBg: 'bg-amber-500/40 dark:bg-amber-500/40',
    socialLinkColor: 'group-hover:text-amber-500 dark:group-hover:text-amber-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-13.png',
    alt: 'Nora Park',
    name: 'Nora Park',
    role: 'Product Operations',
    link: 'mysingleim://ids=nora-park',
    bgColor: 'bg-sky-600/10 dark:bg-sky-600/10',
    avatarBg: 'bg-sky-600/40 dark:bg-sky-600/40',
    socialLinkColor: 'group-hover:text-sky-600 dark:group-hover:text-sky-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-14.png',
    alt: 'Felix Lange',
    name: 'Felix Lange',
    role: 'Security Engineer',
    link: 'mysingleim://ids=felix-lange',
    bgColor: 'bg-indigo-500/10 dark:bg-indigo-500/15',
    avatarBg: 'bg-indigo-500/40 dark:bg-indigo-500/40',
    socialLinkColor: 'group-hover:text-indigo-500 dark:group-hover:text-indigo-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-15.png',
    alt: 'Sara Idris',
    name: 'Sara Idris',
    role: 'QA Lead',
    link: 'mysingleim://ids=sara-idris',
    bgColor: 'bg-green-600/10 dark:bg-green-600/10',
    avatarBg: 'bg-green-600/40 dark:bg-green-600/40',
    socialLinkColor: 'group-hover:text-green-600 dark:group-hover:text-green-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-16.png',
    alt: 'Leo Martin',
    name: 'Leo Martin',
    role: 'Growth Strategist',
    link: 'mysingleim://ids=leo-martin',
    bgColor: 'bg-primary/10',
    avatarBg: 'bg-primary/40',
    socialLinkColor: 'group-hover:text-primary',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-17.png',
    alt: 'Bianca Russo',
    name: 'Bianca Russo',
    role: 'Creative Director',
    link: 'mysingleim://ids=bianca-russo',
    bgColor: 'bg-amber-500/10 dark:bg-amber-500/15',
    avatarBg: 'bg-amber-500/40 dark:bg-amber-500/40',
    socialLinkColor: 'group-hover:text-amber-500 dark:group-hover:text-amber-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-18.png',
    alt: 'Omar Farouk',
    name: 'Omar Farouk',
    role: 'Platform Engineer',
    link: 'mysingleim://ids=omar-farouk',
    bgColor: 'bg-destructive/10',
    avatarBg: 'bg-destructive/40',
    socialLinkColor: 'group-hover:text-destructive',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-19.png',
    alt: 'Chloe Nguyen',
    name: 'Chloe Nguyen',
    role: 'Design Technologist',
    link: 'mysingleim://ids=chloe-nguyen',
    bgColor: 'bg-sky-600/10 dark:bg-sky-600/10',
    avatarBg: 'bg-sky-600/40 dark:bg-sky-600/40',
    socialLinkColor: 'group-hover:text-sky-600 dark:group-hover:text-sky-400',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-20.png',
    alt: 'Daniel Rivera',
    name: 'Daniel Rivera',
    role: 'Finance Lead',
    link: 'mysingleim://ids=daniel-rivera',
    bgColor: 'bg-primary/10',
    avatarBg: 'bg-primary/40',
    socialLinkColor: 'group-hover:text-primary',
  },
  {
    image: 'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-21.png',
    alt: 'Jisoo Han',
    name: 'Jisoo Han',
    role: 'Chief of Staff',
    link: 'mysingleim://ids=jisoo-han',
    bgColor: 'bg-sky-600/10 dark:bg-sky-600/10',
    avatarBg: 'bg-sky-600/40 dark:bg-sky-600/40',
    socialLinkColor: 'group-hover:text-sky-600 dark:group-hover:text-sky-400',
  }
]

import {
  IoAnalyticsOutline,
  IoGitMergeOutline,
  IoGridOutline,
  IoHardwareChipOutline,
  IoLayersOutline,
  IoPulseOutline,
  IoShareSocialOutline,
  IoShieldCheckmarkOutline,
  IoSwapHorizontalOutline
} from 'react-icons/io5'

export const marqueeApps = [
  {
    name: 'Ola',
    description: 'Ola Tech reshapes our access to information.',
    icon: IoHardwareChipOutline,
    connectUrl: 'https://olaelectric.com/'
  },
  {
    name: 'Apple',
    description: 'Apple has transformed our tech connections.',
    icon: IoHardwareChipOutline,
    connectUrl: 'https://www.apple.com/'
  },
  {
    name: 'Notion',
    description: 'Google changed how we find information.',
    icon: IoGridOutline,
    connectUrl: 'https://www.notion.so/'
  },
  {
    name: 'Meta',
    description: 'Meta changed how we connect.',
    icon: IoShareSocialOutline,
    connectUrl: 'https://about.meta.com/'
  },
  {
    name: 'Zoom',
    description: 'Zoom changed how we connect.',
    icon: IoSwapHorizontalOutline,
    connectUrl: 'https://zoom.us/'
  },
  {
    name: 'Framer',
    description: 'Framer revolutionized our data collection.',
    icon: IoLayersOutline,
    connectUrl: 'https://www.framer.com/'
  },
  {
    name: 'Slack',
    description: 'Team collaboration tool.',
    icon: IoPulseOutline,
    connectUrl: 'https://slack.com/'
  },
  {
    name: 'Github',
    description: 'GitHub enhances collaboration.',
    icon: IoGitMergeOutline,
    connectUrl: 'https://github.com/'
  },
  {
    name: 'Discord',
    description: 'Discord transforms our connections.',
    icon: IoShieldCheckmarkOutline,
    connectUrl: 'https://discord.com/'
  },
  {
    name: 'Figma',
    description: 'Figma transformed our connections.',
    icon: IoAnalyticsOutline,
    connectUrl: 'https://www.figma.com/'
  }
]
