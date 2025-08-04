import {
  FileText,
  Users,
  MessageSquare,
  Plus,
  Clock,
  AlertCircle
} from "lucide-react"
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from "@/components/ui/card"
import { StatsCard } from "@/components/ui/stats-card"
import { useNavigate } from "react-router-dom"
import { useToast } from "@/hooks/use-toast"
import { api } from "@/utils/api"

type Stats = {
  totalCVs: number
  extractedCandidates: number
  aiQueries: number
  avgProcessingTime: number
  trends: {
    cvs: number
    candidates: number
    queries: number
    processing: number
  }
}

type RecentFile = {
  cv_id: number
  filename: string
  candidate_name: string
  uploaded_date: string
  status: string
}

type RecentQuery = {
  query: string
  query_type: string
  timestamp: string
}

type DashboardData = {
  stats: Stats
  recent_files: RecentFile[]
  recent_queries: RecentQuery[]
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { toast } = useToast()

  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true)
        setError(null)

        // Fetch stats and recent activity in parallel
        const [statsResponse, recentResponse] = await Promise.all([
          api.dashboard.getStats(),
          api.dashboard.getRecent()
        ])

        // Transform the API response to match our component's expected format
        const transformedData: DashboardData = {
          stats: {
            totalCVs: statsResponse.total_cvs || 0,
            extractedCandidates: statsResponse.processed_cvs || 0,
            aiQueries: statsResponse.total_chats || 0,
            avgProcessingTime: statsResponse.avg_processing_time || 0,
            trends: {
              cvs: statsResponse.trends?.cvs || 0,
              candidates: statsResponse.trends?.candidates || 0,
              queries: statsResponse.trends?.queries || 0,
              processing: statsResponse.trends?.processing || 0
            }
          },
          recent_files: recentResponse.recent_files || [],
          recent_queries: recentResponse.recent_queries || []
        }

        setDashboardData(transformedData)
      } catch (err) {
        console.error("Failed to load dashboard data:", err)
        setError(err instanceof Error ? err.message : "Failed to load dashboard data")
        
        toast({
          title: "Error loading dashboard",
          description: "Failed to fetch dashboard data. Please try refreshing the page.",
          variant: "destructive",
        })
      } finally {
        setLoading(false)
      }
    }

    fetchDashboardData()
  }, [toast])

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000)

    if (diffInSeconds < 60) return 'Just now'
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`
    return `${Math.floor(diffInSeconds / 86400)} days ago`
  }

  const getActivityIcon = (type: string) => {
    return type === 'cv_search' ? 
      <MessageSquare className="h-3 w-3" /> : 
      <FileText className="h-3 w-3" />
  }

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="animate-pulse">
          <div className="h-8 w-64 bg-muted rounded mb-2"></div>
          <div className="h-4 w-96 bg-muted rounded"></div>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-muted rounded-lg animate-pulse"></div>
          ))}
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="h-64 bg-muted rounded-lg animate-pulse"></div>
          <div className="h-64 bg-muted rounded-lg animate-pulse"></div>
        </div>
      </div>
    )
  }

  if (error || !dashboardData) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Welcome to your HR Assistant dashboard
          </p>
        </div>
        
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <div>
                <p className="font-medium">Failed to load dashboard data</p>
                <p className="text-sm text-muted-foreground mt-1">
                  {error || "Please check your connection and try again."}
                </p>
              </div>
            </div>
            <Button 
              className="mt-4" 
              onClick={() => window.location.reload()}
            >
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const { stats, recent_files, recent_queries } = dashboardData

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Welcome back!</h1>
        <p className="text-muted-foreground">
          Here's what's happening with your recruitment process today.
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          title="Total CVs Uploaded"
          value={stats.totalCVs.toString()}
          description="Active candidate profiles"
          icon={<FileText className="h-4 w-4" />}
          trend={{ 
            value: Math.abs(stats.trends.cvs), 
            label: "from last month", 
            positive: stats.trends.cvs >= 0 
          }}
        />
        <StatsCard
          title="Candidates Extracted"
          value={stats.extractedCandidates.toString()}
          description="Successfully processed"
          icon={<Users className="h-4 w-4" />}
          trend={{ 
            value: Math.abs(stats.trends.candidates), 
            label: "from last month", 
            positive: stats.trends.candidates >= 0 
          }}
        />
        <StatsCard
          title="AI Queries Made"
          value={stats.aiQueries.toString()}
          description="Questions asked this month"
          icon={<MessageSquare className="h-4 w-4" />}
          trend={{ 
            value: Math.abs(stats.trends.queries), 
            label: "from last month", 
            positive: stats.trends.queries >= 0 
          }}
        />
        <StatsCard
          title="Processing Time"
          value="5s"
          description="Average CV processing"
          icon={<Clock className="h-4 w-4" />}
          trend={{ 
            value: Math.abs(stats.trends.processing), 
            label: "improvement", 
            positive: stats.trends.processing <= 0 // Lower processing time is better
          }}
        />
      </div>

      {/* Quick Actions & Recent Activity */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>
              Get started with common tasks
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button 
              className="w-full justify-start" 
              onClick={() => navigate("/dashboard/upload")}
            >
              <Plus className="mr-2 h-4 w-4" />
              Upload New CV
            </Button>
            <Button 
              variant="outline" 
              className="w-full justify-start" 
              onClick={() => navigate("/dashboard/ask-ai")}
            >
              <MessageSquare className="mr-2 h-4 w-4" />
              Ask AI Assistant
            </Button>
            <Button 
              variant="outline" 
              className="w-full justify-start" 
              onClick={() => navigate("/dashboard/candidates")}
            >
              <Users className="mr-2 h-4 w-4" />
              View All Candidates
            </Button>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>
              Your latest actions and updates
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Recent File Uploads */}
              {recent_files.slice(0, 3).map((file) => (
                <div key={`file-${file.cv_id}`} className="flex items-start space-x-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-green-500" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground">
                      Uploaded CV: {file.candidate_name || file.filename}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatTimeAgo(file.uploaded_date)} • Status: {file.status}
                    </p>
                  </div>
                </div>
              ))}

              {/* Recent Queries */}
              {recent_queries.slice(0, 3).map((query, index) => (
                <div key={`query-${index}`} className="flex items-start space-x-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-primary" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground">
                      {query.query_type === 'cv_search' ? 'CV Search' : 'AI Query'}: {query.query.substring(0, 50)}...
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatTimeAgo(query.timestamp)}
                    </p>
                  </div>
                </div>
              ))}

              {/* Empty state */}
              {recent_files.length === 0 && recent_queries.length === 0 && (
                <div className="text-center py-6 text-muted-foreground">
                  <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No recent activity</p>
                  <p className="text-xs">Upload a CV or ask a question to get started</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}