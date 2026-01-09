import { BellIcon, SearchIcon } from "lucide-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu"

import { Logo, ThemeColorSelector, ThemeToggle } from "@/components/common"
import { useAuth } from "@/lib/auth"
import { buildProfileImageUrl, resolveProfileAvatarId } from "@/lib/profileImage"
import { cn } from "@/lib/utils"

import NotificationDropdown from "./NotificationDropdown"
import { HomeNavLink } from "./HomeNavLink"
import ProfileDropdown from "./ProfileDropdown"

const HomeNavbar = ({ navigationItems }) => {
  const { user } = useAuth()
  const profileAvatarId = resolveProfileAvatarId(user)
  const avatarSrc = buildProfileImageUrl(profileAvatarId)
  const displayName = user?.username || user?.email || "U"
  const initials = displayName.slice(0, 2).toUpperCase()

  const renderIcon = (Icon) => {
    if (!Icon) return null
    return <Icon className="size-4" />
  }

  return (
    <div className="flex h-full w-full items-center gap-6 px-4 md:px-6">
      <div className="flex flex-1 items-center gap-4">
        <HomeNavLink href="/" className="flex items-center gap-3">
          <Logo className="size-8" />
          <span className="hidden text-xl font-semibold sm:block">Etch AX Portal</span>
        </HomeNavLink>
      </div>

      <NavigationMenu viewport={false} className="hidden flex-1 justify-center lg:flex">
        <NavigationMenuList className="justify-center gap-1">
          {navigationItems.map((navItem) => {
            const Icon = navItem.icon
            if (navItem.href) {
              return (
                <NavigationMenuItem key={navItem.title}>
                  <NavigationMenuLink
                    asChild
                    className={cn(
                      navigationMenuTriggerStyle(),
                      "flex flex-row items-center gap-1.5",
                    )}
                  >
                    <HomeNavLink href={navItem.href}>
                      {renderIcon(Icon)}
                      {navItem.title}
                    </HomeNavLink>
                  </NavigationMenuLink>
                </NavigationMenuItem>
              )
            }

            return (
              <NavigationMenuItem key={navItem.title}>
                <NavigationMenuTrigger className="gap-1.5">
                  {renderIcon(Icon)}
                  {navItem.title}
                </NavigationMenuTrigger>
                <NavigationMenuContent className="data-[motion=from-start]:slide-in-from-left-30! data-[motion=to-start]:slide-out-to-left-30! data-[motion=from-end]:slide-in-from-right-30! data-[motion=to-end]:slide-out-to-right-30! absolute w-auto">
                  <ul className="grid w-38 gap-4 p-2">
                    <li>
                      {navItem.items?.map((item) => (
                        <NavigationMenuLink key={item.title} asChild>
                          <HomeNavLink href={item.href} className="block px-3 py-1.5">
                            {item.title}
                          </HomeNavLink>
                        </NavigationMenuLink>
                      ))}
                    </li>
                  </ul>
                </NavigationMenuContent>
              </NavigationMenuItem>
            )
          })}
        </NavigationMenuList>
      </NavigationMenu>

      <div className="flex flex-1 items-center justify-end gap-2 md:gap-4">
        <Button variant="ghost" size="icon" className="flex md:hidden">
          <SearchIcon />
        </Button>
        <ThemeToggle />
        <ThemeColorSelector />
        <NotificationDropdown
          trigger={
            <Button variant="ghost" size="icon" className="relative">
              <BellIcon />
              <span className="bg-destructive absolute right-2.5 top-2 size-2 rounded-full" />
            </Button>
          }
        />
        <ProfileDropdown
          trigger={
            <Button variant="ghost" className="h-full p-0">
              <Avatar className="size-9.5 rounded-md">
                <AvatarImage src={avatarSrc || undefined} alt={displayName} />
                <AvatarFallback>{initials}</AvatarFallback>
              </Avatar>
            </Button>
          }
        />
      </div>
    </div>
  )
}

export default HomeNavbar
