import { 
  BarChart3, 
  Upload, 
  MessageSquare, 
  Users, 
  Settings,
  Brain
} from "lucide-react"
import { NavLink, useLocation } from "react-router-dom"

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

const navigation = [
  { title: "Dashboard", url: "/dashboard", icon: BarChart3 },
  { title: "Upload CV", url: "/dashboard/upload", icon: Upload },
  { title: "Ask AI", url: "/dashboard/ask-ai", icon: MessageSquare },
  { title: "Candidates", url: "/dashboard/candidates", icon: Users },
  { title: "Settings", url: "/dashboard/settings", icon: Settings },
]

export function AppSidebar() {
  const { state } = useSidebar()
  const location = useLocation()
  const currentPath = location.pathname
  const collapsed = state === "collapsed"

  const isActive = (path: string) => {
    if (path === "/dashboard" && currentPath === "/dashboard") return true
    if (path !== "/dashboard" && currentPath.startsWith(path)) return true
    return false
  }

  return (
    <Sidebar
      className={collapsed ? "w-16" : "w-64"}
      collapsible="icon"
    >
      <SidebarContent className="border-r border-sidebar-border">
        {/* Logo section */}
        <div className="p-4 border-b border-sidebar-border">
          <div className="flex items-center gap-2">
            <div className="w-14 h-14 rounded-lg flex items-center justify-center">
            <img src="/icon.png" alt="HR Logo" className="w-14 h-14 text-primary-foreground" />
            </div>
            {!collapsed && (
              <div>
                <h1 className="font-semibold text-sidebar-foreground">HR Assistant</h1>
                <p className="text-xs text-sidebar-foreground/60">AI-Powered Recruiting</p>
              </div>
            )}
          </div>
        </div>

        <SidebarGroup className="px-2 py-4">
          <SidebarGroupLabel className={collapsed ? "sr-only" : ""}>
            Navigation
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navigation.map((item) => {
                const active = isActive(item.url)
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild className="h-10">
                      <NavLink 
                        to={item.url}
                        className={
                          active 
                            ? "bg-primary text-primary-foreground font-medium" 
                            : "hover:bg-accent hover:text-accent-foreground transition-colors"
                        }
                      >
                        <item.icon className="w-5 h-5 flex-shrink-0" />
                        {!collapsed && <span>{item.title}</span>}
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}