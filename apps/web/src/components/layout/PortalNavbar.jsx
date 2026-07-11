import { useEffect, useRef, useState } from "react"
import { useLocation } from "react-router-dom"
import { SearchIcon } from "lucide-react"

import { GaNEtchLogo, ThemeColorSelector, ThemeToggle } from "@/components/common"
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
import { useAuth } from "@/lib/auth"
import { hasAnyAppAccess, hasEveryAppAccess } from "@/lib/access/appAccess"
import { PORTAL_BRAND_KEY, resolvePortalBrand } from "@/lib/config/portalBranding"
import { buildProfileImageUrl, resolveProfileAvatarId } from "@/lib/profileImage"
import { useTheme } from "@/lib/theme"
import { cn } from "@/lib/utils"

import { PortalNavLink } from "./PortalNavLink"
import { PortalProfileDropdown } from "./PortalProfileDropdown"

const NAV_HIDE_DELAY_MS = 3000
const NAV_ICON_CLASS_NAME = "size-4"
const NAV_MENU_LINK_CLASS_NAME = "flex flex-row items-center gap-1.5"
const NAV_MENU_TRIGGER_CLASS_NAME = "gap-1.5"
const NAV_MENU_CONTENT_CLASS_NAME =
  "data-[motion=from-start]:slide-in-from-left-30! data-[motion=to-start]:slide-out-to-left-30! data-[motion=from-end]:slide-in-from-right-30! data-[motion=to-end]:slide-out-to-right-30! absolute z-50 w-auto"
const NAV_SUB_LINK_CLASS_NAME = "block whitespace-nowrap px-3 py-1.5"

function canShowNavigationItem(item, user) {
  if (item?.requireSuperuser && !user?.is_superuser) return false
  if (item?.anyAppScopes) return hasAnyAppAccess(user, item.anyAppScopes)
  const requiredScopes = item?.requiredAppScopes || (item?.appScope ? [item.appScope] : [])
  return hasEveryAppAccess(user, requiredScopes)
}

export function PortalNavbar({ navigationItems }) {
  const { user } = useAuth()
  const { theme = "system", systemTheme } = useTheme()
  const { pathname } = useLocation()
  const isHomeRoute = pathname === "/"
  const shouldFadeNavItems = !isHomeRoute
  const hideTimerRef = useRef(null)
  const [isNavVisible, setIsNavVisible] = useState(() => pathname === "/")

  useEffect(() => {
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current)
      hideTimerRef.current = null
    }

    if (!shouldFadeNavItems) {
      setIsNavVisible(true)
      return
    }

    setIsNavVisible(false)
  }, [shouldFadeNavItems])

  useEffect(() => {
    return () => {
      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current)
        hideTimerRef.current = null
      }
    }
  }, [])

  const showNavItems = () => {
    if (!shouldFadeNavItems) return
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current)
      hideTimerRef.current = null
    }
    setIsNavVisible(true)
  }

  const scheduleHideNavItems = () => {
    if (!shouldFadeNavItems) return
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current)
    }
    hideTimerRef.current = setTimeout(() => {
      setIsNavVisible(false)
      hideTimerRef.current = null
    }, NAV_HIDE_DELAY_MS)
  }

  const handleBlur = (event) => {
    if (event.currentTarget.contains(event.relatedTarget)) {
      return
    }
    scheduleHideNavItems()
  }

  const navItemVisibilityClassName = shouldFadeNavItems
    ? cn(
      "transition-opacity duration-700",
      isNavVisible ? "opacity-100" : "opacity-0 pointer-events-none",
    )
    : ""
  const profileAvatarId = resolveProfileAvatarId(user)
  const avatarSrc = buildProfileImageUrl(profileAvatarId)
  const displayName = user?.username || user?.email || "U"
  const initials = displayName.slice(0, 1).toUpperCase()

  const renderIcon = (Icon) => {
    if (!Icon) return null
    return <Icon className={NAV_ICON_CLASS_NAME} />
  }

  const visibleNavigationItems = navigationItems
    .map((navItem) => ({
      ...navItem,
      items: navItem.items?.filter((item) => canShowNavigationItem(item, user)),
    }))
    .filter((navItem) => canShowNavigationItem(navItem, user))
    .filter((navItem) => navItem.href || (Array.isArray(navItem.items) && navItem.items.length > 0))
  const brand = resolvePortalBrand(pathname)
  const brandMark = brand.mark
  const BrandIcon = brandMark?.type === "icon" ? brandMark.icon : null
  const resolvedTheme = theme === "system" ? systemTheme : theme
  const brandImageSrc =
    brandMark?.type === "image" && resolvedTheme === "dark" && brandMark.darkSrc
      ? brandMark.darkSrc
      : brandMark?.src
  const shouldUsePortalLogo = brand.key === PORTAL_BRAND_KEY

  return (
    <div
      className="flex h-full w-full items-center gap-6 px-4 md:px-6"
      onMouseEnter={showNavItems}
      onMouseLeave={scheduleHideNavItems}
      onFocusCapture={showNavItems}
      onBlurCapture={handleBlur}
    >
      <div className="flex flex-1 items-center gap-4">
        <PortalNavLink href="/" className="flex items-center gap-3">
          <span className="flex size-8 shrink-0 items-center justify-center">
            {shouldUsePortalLogo ? (
              <GaNEtchLogo className="react-logo-circles--navbar" compact decorative />
            ) : null}
            {!shouldUsePortalLogo && brandMark?.type === "image" ? (
              <img
                src={brandImageSrc}
                alt={brandMark.alt ?? brand.name}
                className="size-8 object-contain"
              />
            ) : null}
            {!shouldUsePortalLogo && BrandIcon ? <BrandIcon className="size-4" aria-hidden="true" /> : null}
          </span>
          <span className="hidden text-xl font-semibold sm:block">{brand.name}</span>
        </PortalNavLink>
      </div>

      <NavigationMenu
        viewport={false}
        className="hidden flex-1 justify-center lg:flex"
      >
        <NavigationMenuList className="justify-center gap-1">
          {visibleNavigationItems.map((navItem) => {
            const Icon = navItem.icon
            if (navItem.href) {
              return (
                <NavigationMenuItem key={navItem.title}>
                  <NavigationMenuLink
                    asChild
                    className={cn(
                      navigationMenuTriggerStyle(),
                      NAV_MENU_LINK_CLASS_NAME,
                      navItemVisibilityClassName,
                    )}
                  >
                    <PortalNavLink href={navItem.href}>
                      {renderIcon(Icon)}
                      {navItem.title}
                    </PortalNavLink>
                  </NavigationMenuLink>
                </NavigationMenuItem>
              )
            }

            return (
              <NavigationMenuItem key={navItem.title}>
                <NavigationMenuTrigger
                  className={cn(NAV_MENU_TRIGGER_CLASS_NAME, navItemVisibilityClassName)}
                >
                  {renderIcon(Icon)}
                  {navItem.title}
                </NavigationMenuTrigger>
                <NavigationMenuContent className={NAV_MENU_CONTENT_CLASS_NAME}>
                  <ul className="grid w-max gap-4 p-2">
                    <li>
                      {navItem.items?.map((item) => (
                        <NavigationMenuLink key={item.title} asChild>
                          {item.external ? (
                            <a
                              href={item.href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={cn(NAV_SUB_LINK_CLASS_NAME, "flex items-center gap-2")}
                            >
                              {renderIcon(item.icon)}
                              {item.title}
                            </a>
                          ) : (
                            <PortalNavLink
                              href={item.href}
                              className={cn(NAV_SUB_LINK_CLASS_NAME, "flex items-center gap-2")}
                            >
                              {renderIcon(item.icon)}
                              {item.title}
                            </PortalNavLink>
                          )}
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
        <PortalProfileDropdown
          trigger={
            <Button variant="ghost" className="h-full p-0">
              <Avatar className="size-9.5 rounded-full">
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
