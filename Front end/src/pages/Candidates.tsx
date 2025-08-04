import { useState, useEffect } from "react"
import { Search, Filter, Download, Eye, MoreHorizontal, FileText, MapPin, Calendar, Star, AlertCircle, Trash2, X, Mail, Phone, Building, GraduationCap, Briefcase, User, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from "@/components/ui/dropdown-menu"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { useToast } from "@/hooks/use-toast"
import { api } from "@/utils/api"
import { useNavigate } from "react-router-dom"

interface Candidate {
  cv_id: number
  filename: string
  candidate_name: string
  candidate_email: string
  candidate_phone: string
  processing_status: string
  uploaded_date: string
  skills: string[]
  experience: Array<{
    Role?: string
    role?: string
    company?: string
    Company?: string
    duration?: string
  }>
  education: Array<{
    degree?: string
    school?: string
    year?: string
  }>
}

interface CandidateDetail extends Candidate {
    summary?: {
    Name?: string
    Email?: string
    Phone?: string
    Education?: {
      Degree?: string
      School?: string
      Year?: string
    }[]
    Experience?: {
      Company?: string
      Role?: string
      Duration?: string
    }[]
    Skills?: string[]
    Languages?: string[]
  }
  location?: string
  languages?: string[]
  certifications?: string[]
  raw_text?: string
}

interface CandidatesResponse {
  candidates: Candidate[]
  total_count: number
  search_query: string | null
  user_id: number
}

export default function Candidates() {
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [searchTerm, setSearchTerm] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [totalCount, setTotalCount] = useState(0)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateDetail | null>(null)
  const [candidateModalOpen, setCandidateModalOpen] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [downloadingId, setDownloadingId] = useState<number | null>(null)
  
  const { toast } = useToast()
  const navigate = useNavigate()

  const fetchCandidates = async (search?: string) => {
    try {
      setLoading(true)
      setError("")
      
      const data: CandidatesResponse = await api.candidates.getAll(50, search)
      
      setCandidates(data.candidates || [])
      setTotalCount(data.total_count || 0)
    } catch (err: any) {
      console.error("Failed to fetch candidates:", err)
      setError(err.message || "Failed to load candidates.")
      
      toast({
        title: "Error loading candidates",
        description: err.message || "Failed to fetch candidates. Please try again.",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCandidates()
  }, [])

  // Debounced search
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchTerm.trim()) {
        fetchCandidates(searchTerm)
      } else if (searchTerm === "") {
        fetchCandidates()
      }
    }, 500)

    return () => clearTimeout(timeoutId)
  }, [searchTerm])

  const handleViewCandidate = async (cvId: number) => {
    try {
      setLoadingDetail(true)
      setCandidateModalOpen(true)
      
      const candidateDetail: CandidateDetail = await api.candidates.getDetail(cvId)
      setSelectedCandidate(candidateDetail)
      
    } catch (err: any) {
      toast({
        title: "Error",
        description: "Failed to load candidate details.",
        variant: "destructive",
      })
      setCandidateModalOpen(false)
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleDeleteCandidate = async (cvId: number, candidateName: string) => {
    if (!confirm(`Are you sure you want to delete ${candidateName}'s CV? This action cannot be undone.`)) {
      return
    }

    try {
      setDeletingId(cvId)
      await api.cvs.delete(cvId)
      
      // Remove from local state
      setCandidates(prev => prev.filter(c => c.cv_id !== cvId))
      setTotalCount(prev => prev - 1)
      
      toast({
        title: "Candidate deleted",
        description: `${candidateName}'s CV has been deleted successfully.`,
      })
    } catch (err: any) {
      toast({
        title: "Delete failed",
        description: err.message || "Failed to delete candidate.",
        variant: "destructive",
      })
    } finally {
      setDeletingId(null)
    }
  }

  const handleDownloadCV = async (candidate: Candidate) => {
    try {
      setDownloadingId(candidate.cv_id)
      
    const blob = await api.files.download(candidate.cv_id);
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = candidate.filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
      
      toast({
        title: "Download started",
        description: `Downloading ${candidate.filename}`,
      })
    } catch (err: any) {
      toast({
        title: "Download failed",
        description: err.message || "Failed to download CV.",
        variant: "destructive",
      })
    } finally {
      setDownloadingId(null)
    }
  }

  const handleViewPDF = async (cvId: number, filename: string) => {
    const blob = await api.files.view(cvId);
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
    
    toast({
      title: "Opening PDF",
      description: `Opening ${filename} in new tab`,
    })
  }

  const handleExportCandidates = async () => {
    try {
      setExporting(true)
      
      // Generate CSV content from candidates data
      const csvHeaders = [
        'Name',
        'Email',
        'Phone',
        'Current Role',
        'Company',
        'Skills',
        'Education',
        'Status',
        'Upload Date',
        'Filename'
      ]
      
      const csvRows = candidates.map(candidate => [
        candidate.candidate_name || 'Unknown',
        candidate.candidate_email || '',
        candidate.candidate_phone || '',
        candidate.experience?.[0]?.Role || '',
        candidate.experience?.[0]?.Company || '',
        candidate.skills?.join('; ') || '',
        candidate.education?.map(edu => `${edu.degree} - ${edu.school}`).join('; ') || '',
        candidate.processing_status,
        formatDate(candidate.uploaded_date),
        candidate.filename
      ])
      
      const csvContent = [
        csvHeaders.join(','),
        ...csvRows.map(row => row.map(cell => `"${cell.replace(/"/g, '""')}"`).join(','))
      ].join('\n')
      
      // Create and download CSV file
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
      const link = document.createElement('a')
      const url = URL.createObjectURL(blob)
      link.setAttribute('href', url)
      link.setAttribute('download', `candidates_export_${new Date().toISOString().split('T')[0]}.csv`)
      link.style.visibility = 'hidden'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      toast({
        title: "Export completed",
        description: `Exported ${candidates.length} candidates to CSV`,
      })
    } catch (err: any) {
      toast({
        title: "Export failed",
        description: err.message || "Failed to export candidates.",
        variant: "destructive",
      })
    } finally {
      setExporting(false)
    }
  }

  const getInitials = (name: string) => {
    if (!name || name === 'Unknown') return 'U'
    return name.split(' ').map(part => part[0]).join('').toUpperCase().substring(0, 2)
  }

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString)
      return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
      })
    } catch {
      return dateString
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'fully_processed':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'
      case 'partially_processed':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300'
      case 'processing_failed':
      case 'extraction_failed':
      case 'summarization_failed':
      case 'embedding_failed':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'fully_processed':
        return 'Processed'
      case 'partially_processed':
        return 'Partial'
      case 'processing_failed':
        return 'Failed'
      case 'text_extracted_only':
        return 'Text Only'
      default:
        return status.replace('_', ' ')
    }
  }

  const renderSummary = (summary: string | object | undefined) => {
    if (!summary) return null
    
    if (typeof summary === 'string') {
      return summary
    }
    
    if (typeof summary === 'object') {
      // If summary is an object, try to extract meaningful text
      if ('text' in summary) {
        return String(summary.text)
      }
      if ('summary' in summary) {
        return String(summary.summary)
      }
      // As a fallback, stringify the object (though this isn't ideal)
      return JSON.stringify(summary)
    }
    
    return String(summary)
  }

  const CandidateDetailModal = () => (
    <Dialog open={candidateModalOpen} onOpenChange={setCandidateModalOpen}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <Avatar className="h-12 w-12">
              <AvatarFallback className="bg-primary text-primary-foreground">
                {selectedCandidate ? getInitials(selectedCandidate.candidate_name) : 'U'}
              </AvatarFallback>
            </Avatar>
            <div>
              <h2 className="text-2xl font-bold">
                {selectedCandidate?.candidate_name || 'Unknown'}
              </h2>
              <p className="text-muted-foreground">
                {selectedCandidate?.experience?.[0]?.Role || 'Position not specified'}
              </p>
            </div>
          </DialogTitle>
        </DialogHeader>

        {loadingDetail ? (
          <div className="space-y-4 animate-pulse">
            <div className="h-4 bg-muted rounded w-full"></div>
            <div className="h-4 bg-muted rounded w-3/4"></div>
            <div className="h-4 bg-muted rounded w-1/2"></div>
          </div>
        ) : selectedCandidate ? (
          <div className="space-y-6">
            {/* Contact Information */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <User className="h-5 w-5" />
                    Contact Information
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {selectedCandidate.candidate_email && (
                    <div className="flex items-center gap-2">
                      <Mail className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm">{selectedCandidate.candidate_email}</span>
                    </div>
                  )}
                  {selectedCandidate.candidate_phone && (
                    <div className="flex items-center gap-2">
                      <Phone className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm">{selectedCandidate.candidate_phone}</span>
                    </div>
                  )}
                  {selectedCandidate.location && (
                    <div className="flex items-center gap-2">
                      <MapPin className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm">{selectedCandidate.location}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <Badge className={getStatusColor(selectedCandidate.processing_status)}>
                      {getStatusText(selectedCandidate.processing_status)}
                    </Badge>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Document Info
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="text-sm">
                    <span className="font-medium">Filename:</span> {selectedCandidate.filename}
                  </div>
                  <div className="text-sm">
                    <span className="font-medium">Uploaded:</span> {formatDate(selectedCandidate.uploaded_date)}
                  </div>
                  <div className="flex gap-2">
                    <Button 
                      size="sm" 
                      onClick={() => handleViewPDF(selectedCandidate.cv_id, selectedCandidate.filename)}
                      className="flex items-center gap-1"
                    >
                      <ExternalLink className="h-3 w-3" />
                      View PDF
                    </Button>
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => handleDownloadCV(selectedCandidate)}
                      disabled={downloadingId === selectedCandidate.cv_id}
                    >
                      <Download className="h-3 w-3 mr-1" />
                      {downloadingId === selectedCandidate.cv_id ? 'Downloading...' : 'Download'}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Skills */}
            {(selectedCandidate.skills?.length || selectedCandidate.summary?.Skills?.length) > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">Skills</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {(selectedCandidate.skills || selectedCandidate.summary?.Skills).map((skill, index) => (
                      <Badge key={index} variant="secondary">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Experience */}
            {(selectedCandidate.experience?.length || selectedCandidate.summary?.Experience?.length) > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Briefcase className="h-5 w-5" />
                    Experience
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {(selectedCandidate.experience || selectedCandidate.summary?.Experience).map((exp, index) => (
                      <div key={index} className="border-l-2 border-primary pl-4">
                        <h4 className="font-medium">{exp.Role || exp.role || 'Position not specified'}</h4>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Building className="h-3 w-3" />
                          <span>{exp.Company || exp.company || 'Company not specified'}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {(selectedCandidate.education?.length || selectedCandidate.summary?.Education?.length) > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <GraduationCap className="h-5 w-5" />
                    Education
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {(selectedCandidate.education || selectedCandidate.summary?.Education).map((edu, index) => (
                      <div key={index} className="border-l-2 border-secondary pl-4">
                        <h4 className="font-medium">{edu.Degree || edu.degree || 'Degree not specified'}</h4>
                        <div className="text-sm text-muted-foreground">
                          {edu.School || edu.school || 'School not specified'}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {(selectedCandidate.languages?.length || selectedCandidate.summary?.Languages?.length) > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">Languages</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {(selectedCandidate.languages || selectedCandidate.summary?.Languages).map((lang, index) => (
                      <Badge key={index} variant="outline">
                        {lang}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Candidates</h1>
          <p className="text-muted-foreground">
            Browse and manage your candidate database
            {totalCount > 0 && ` (${totalCount} total)`}
          </p>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center space-x-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search candidates, skills, or positions..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>
        <Button 
          variant="outline" 
          onClick={handleExportCandidates}
          disabled={exporting || candidates.length === 0}
        >
          <Download className="mr-2 h-4 w-4" />
          {exporting ? 'Exporting...' : 'Export CSV'}
        </Button>
        <Button onClick={() => navigate('/dashboard/upload')}>
          Upload CV
        </Button>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader className="pb-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="h-12 w-12 bg-muted rounded-full"></div>
                    <div className="space-y-2">
                      <div className="h-4 w-24 bg-muted rounded"></div>
                      <div className="h-3 w-20 bg-muted rounded"></div>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="h-3 w-full bg-muted rounded"></div>
                <div className="h-3 w-3/4 bg-muted rounded"></div>
                <div className="flex gap-2">
                  <div className="h-6 w-16 bg-muted rounded"></div>
                  <div className="h-6 w-16 bg-muted rounded"></div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Error State */}
      {!loading && error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <div>
                <p className="font-medium">Failed to load candidates</p>
                <p className="text-sm text-muted-foreground mt-1">{error}</p>
              </div>
            </div>
            <Button 
              className="mt-4" 
              onClick={() => fetchCandidates()}
            >
              Try Again
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Candidates Grid */}
      {!loading && !error && candidates.length > 0 && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {candidates.map((candidate) => (
            <Card key={candidate.cv_id} className="hover:shadow-md transition-shadow">
              <CardHeader className="pb-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <Avatar className="h-12 w-12">
                      <AvatarFallback className="bg-primary text-primary-foreground">
                        {getInitials(candidate.candidate_name)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="min-w-0 flex-1">
                      <CardTitle className="text-lg truncate">
                        {candidate.candidate_name || 'Unknown'}
                      </CardTitle>
                      <CardDescription className="truncate">
                        {candidate.experience?.[0]?.Role || 'Position not specified'}
                      </CardDescription>
                    </div>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8 flex-shrink-0">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleViewCandidate(candidate.cv_id)}>
                        <Eye className="mr-2 h-4 w-4" />
                        View Details
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleViewPDF(candidate.cv_id, candidate.filename)}>
                        <ExternalLink className="mr-2 h-4 w-4" />
                        View PDF
                      </DropdownMenuItem>
                      <DropdownMenuItem 
                        onClick={() => handleDownloadCV(candidate)}
                        disabled={downloadingId === candidate.cv_id}
                      >
                        <FileText className="mr-2 h-4 w-4" />
                        {downloadingId === candidate.cv_id ? 'Downloading...' : 'Download CV'}
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem 
                        onClick={() => handleDeleteCandidate(candidate.cv_id, candidate.candidate_name)}
                        className="text-destructive focus:text-destructive"
                        disabled={deletingId === candidate.cv_id}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        {deletingId === candidate.cv_id ? 'Deleting...' : 'Delete CV'}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                  <div className="flex items-center min-w-0 flex-1">
                    <MapPin className="mr-1 h-3 w-3 flex-shrink-0" />
                    <span className="truncate">
                      {candidate.experience?.[0]?.Company || 'Company not specified'}
                    </span>
                  </div>
                  <Badge 
                    variant="outline" 
                    className={`text-xs ${getStatusColor(candidate.processing_status)}`}
                  >
                    {getStatusText(candidate.processing_status)}
                  </Badge>
                </div>

                {/* Contact Info */}
                {(candidate.candidate_email || candidate.candidate_phone) && (
                  <div className="text-sm text-muted-foreground space-y-1">
                    {candidate.candidate_email && (
                      <div className="truncate">📧 {candidate.candidate_email}</div>
                    )}
                    {candidate.candidate_phone && (
                      <div>📞 {candidate.candidate_phone}</div>
                    )}
                  </div>
                )}

                {/* Skills */}
                <div className="flex flex-wrap gap-1">
                  {Array.isArray(candidate.skills) &&
                  candidate.skills.slice(0, 3).map((skill, index) => (
                    <Badge key={index} variant="secondary" className="text-xs">
                      {skill}
                    </Badge>
                  ))}
                  {candidate.skills?.length > 3 && (
                    <Badge variant="outline" className="text-xs">
                      +{candidate.skills.length - 3} more
                    </Badge>
                  )}
                  {(!candidate.skills || candidate.skills.length === 0) && (
                    <span className="text-xs text-muted-foreground">No skills listed</span>
                  )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between pt-2 border-t border-border text-xs text-muted-foreground">
                  <span className="truncate">
                    {candidate.filename}
                  </span>
                  <span className="flex-shrink-0 ml-2">
                    {formatDate(candidate.uploaded_date)}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && candidates.length === 0 && (
        <div className="text-center py-12">
          <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <h3 className="text-lg font-medium mb-2">
            {searchTerm ? 'No candidates found' : 'No candidates yet'}
          </h3>
          <p className="text-muted-foreground mb-4">
            {searchTerm 
              ? 'Try adjusting your search terms or check your spelling'
              : 'Upload some CVs to start building your candidate database'
            }
          </p>
          {!searchTerm && (
            <Button onClick={() => navigate('/dashboard/upload')}>
              Upload Your First CV
            </Button>
          )}
        </div>
      )}

      {/* Candidate Detail Modal */}
      <CandidateDetailModal />
    </div>
  )
}