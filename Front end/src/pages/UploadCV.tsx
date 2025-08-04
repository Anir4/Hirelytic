import { useState, useEffect, useRef } from "react"
import { Upload, FileText, CheckCircle, XCircle, Loader2, Clock, Trash2, Eye, Download, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import { api } from "@/utils/api"

interface UploadedFile {
  cv_id: number
  filename: string
  candidate_name: string
  candidate_email: string
  candidate_phone: string
  processing_status: string
  uploaded_date: string
  updated_date: string
}

export default function UploadCV() {
  const [isDragging, setIsDragging] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<string>("")
  const [error, setError] = useState<string>("")
  const [success, setSuccess] = useState<string>("")
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Fetch uploaded files on load
  useEffect(() => {
    fetchFiles()
  }, [])

  const fetchFiles = async () => {
    try {
      setError("")
      const data = await api.cvs.getAll(50) // Get up to 50 files
      setUploadedFiles(data.files || [])
    } catch (error) {
      console.error("Failed to fetch files:", error)
      setError("Failed to load uploaded files. Please refresh the page.")
    }
  }

  const uploadFile = async (file: File) => {
    if (file.type !== "application/pdf") {
      setError("Only PDF files are allowed")
      return
    }

    if (file.size > 50 * 1024 * 1024) { // 50MB limit
      setError("File size must be less than 50MB")
      return
    }

    try {
      setIsUploading(true)
      setError("")
      setSuccess("")
      //setUploadProgress("Uploading file...")

      const response = await api.cvs.upload(file)

      if (response) {
        let statusMessage = response.message
        
        if (response.reprocessed) {
          statusMessage += " (reprocessed)"
        }
        
        if (response.warnings && response.warnings.length > 0) {
          statusMessage += ` with warnings: ${response.warnings.join(", ")}`
        }
        
        setSuccess(statusMessage)
        
        // Refresh the file list
        await fetchFiles()
        
        // Clear the file input
        if (fileInputRef.current) {
          fileInputRef.current.value = ""
        }
      }
    } catch (error) {
      console.error("Upload error:", error)
      setError(error.message || "Upload failed. Please try again.")
    } finally {
      setIsUploading(false)
    }
  }

  const uploadFiles = async (files: FileList) => {
    const pdfFiles = Array.from(files).filter(file => file.type === "application/pdf")
    
    if (pdfFiles.length === 0) {
      setError("No PDF files found. Please select PDF files only.")
      return
    }

    if (pdfFiles.length > 1) {
      setError("Please upload one file at a time for better processing.")
      return
    }

    // Upload files one by one
    for (const file of pdfFiles) {
      await uploadFile(file)
    }
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      uploadFiles(e.target.files)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      uploadFiles(e.dataTransfer.files)
    }
  }

  const handleChooseFiles = () => {
    fileInputRef.current?.click()
  }

  const handleDeleteFile = async (cvId: number, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
      return
    }

    try {
      await api.cvs.delete(cvId)
      setSuccess(`File "${filename}" deleted successfully`)
      await fetchFiles() // Refresh the list
    } catch (error) {
      console.error("Delete error:", error)
      setError(error.message || "Failed to delete file")
    }
  }

  const handleViewFile = async (cvId: number, filename: string) => {
    try {
      const blob = await api.files.view(cvId)
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank')
      
      // Clean up the URL after a delay
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error) {
      console.error("View error:", error)
      setError(error.message || "Failed to view file")
    }
  }

  const handleDownloadFile = async (cvId: number, filename: string) => {
    try {
      const blob = await api.files.download(cvId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error("Download error:", error)
      setError(error.message || "Failed to download file")
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "fully_processed":
        return <CheckCircle className="h-4 w-4 text-green-600" />
      case "partially_processed":
      case "text_extracted_only":
        return <AlertCircle className="h-4 w-4 text-yellow-600" />
      case "uploading":
      case "text_extracted":
      case "summarized":
        return <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
      case "extraction_failed":
      case "summarization_failed":
      case "embedding_failed":
        return <XCircle className="h-4 w-4 text-red-600" />
      default:
        return <Clock className="h-4 w-4 text-gray-600" />
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "fully_processed":
        return <Badge className="bg-green-100 text-green-800 border-green-200">Ready</Badge>
      case "partially_processed":
        return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200">Partial</Badge>
      case "text_extracted_only":
        return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200">Text Only</Badge>
      case "uploading":
      case "text_extracted":
      case "summarized":
        return <Badge className="bg-blue-100 text-blue-800 border-blue-200">Processing</Badge>
      case "extraction_failed":
      case "summarization_failed":
      case "embedding_failed":
        return <Badge className="bg-red-100 text-red-800 border-red-200">Failed</Badge>
      default:
        return <Badge variant="outline">Unknown</Badge>
    }
  }

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString()
    } catch {
      return dateString
    }
  }

  const getStatusDescription = (status: string) => {
    switch (status) {
      case "fully_processed":
        return "Ready for search and analysis"
      case "partially_processed":
        return "Processing incomplete - some features may not work"
      case "text_extracted_only":
        return "Text extracted but not summarized or indexed"
      case "uploading":
        return "File is being uploaded..."
      case "text_extracted":
        return "Extracting text from PDF..."
      case "summarized":
        return "Creating AI summary and extracting information..."
      case "extraction_failed":
        return "Failed to extract text from PDF"
      case "summarization_failed":
        return "Failed to create AI summary"
      case "embedding_failed":
        return "Failed to create search index"
      default:
        return "Unknown status"
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Upload CV</h1>
        <p className="text-muted-foreground">
          Upload candidate resumes in PDF format for AI analysis and semantic search
        </p>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <Alert className="border-red-200 bg-red-50">
          <AlertCircle className="h-4 w-4 text-red-600" />
          <AlertDescription className="text-red-800">{error}</AlertDescription>
        </Alert>
      )}
      
      {success && (
        <Alert className="border-green-200 bg-green-50">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">{success}</AlertDescription>
        </Alert>
      )}

      {/* Upload Area */}
      <Card>
        <CardHeader>
          <CardTitle>Upload New CV</CardTitle>
          <CardDescription>
            Drag and drop your PDF file here or click to browse. Files will be processed automatically.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div
            className={cn(
              "border-2 border-dashed rounded-lg p-12 text-center transition-colors",
              isDragging 
                ? "border-primary bg-primary/5" 
                : "border-border hover:border-primary/50",
              isUploading && "opacity-50 pointer-events-none"
            )}
            onDragOver={(e) => {
              e.preventDefault()
              if (!isUploading) setIsDragging(true)
            }}
            onDragLeave={(e) => {
              e.preventDefault()
              setIsDragging(false)
            }}
            onDrop={handleDrop}
          >
            <Upload className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <div className="space-y-2">
              <p className="text-lg font-medium">
                {isUploading ? "Processing..." : "Drop your PDF file here"}
              </p>
              <p className="text-sm text-muted-foreground">
                {isUploading ? uploadProgress : "or click to browse your computer"}
              </p>
              {isUploading && (
                <div className="mt-4">
                  <Loader2 className="animate-spin h-6 w-6 mx-auto text-primary" />
                </div>
              )}
            </div>
            <input 
              type="file" 
              accept="application/pdf"
              className="hidden"
              ref={fileInputRef}
              onChange={handleFileInputChange}
              disabled={isUploading}
            />
            <Button 
              className="mt-6" 
              onClick={handleChooseFiles} 
              disabled={isUploading}
            >
              {isUploading ? (
                <>
                  <Loader2 className="animate-spin h-4 w-4 mr-2" />
                  Processing...
                </>
              ) : (
                "Choose File"
              )}
            </Button>
          </div>
          <div className="mt-4 text-sm text-muted-foreground">
            <p>• Only PDF files are supported</p>
            <p>• Maximum file size: 50MB</p>
            <p>• Processing includes text extraction, AI summarization, and search indexing</p>
          </div>
        </CardContent>
      </Card>

      {/* Upload Status */}
      <Card>
        <CardHeader>
          <CardTitle>Uploaded CVs ({uploadedFiles.length})</CardTitle>
          <CardDescription>
            Track the processing status of your uploaded files
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {uploadedFiles.length === 0 ? (
              <div className="text-center py-8">
                <FileText className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground">No files uploaded yet.</p>
                <p className="text-sm text-muted-foreground mt-2">
                  Upload your first CV to get started with AI-powered candidate analysis.
                </p>
              </div>
            ) : (
              uploadedFiles.map((file) => (
                <div 
                  key={file.cv_id}
                  className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                >
                  <div className="flex items-center space-x-4 flex-1">
                    <FileText className="h-8 w-8 text-muted-foreground flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center space-x-2 mb-1">
                        <p className="font-medium truncate">{file.filename}</p>
                        {getStatusBadge(file.processing_status)}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {file.candidate_name && file.candidate_name !== 'Unknown' ? (
                          <>Candidate: {file.candidate_name}</>
                        ) : (
                          <>Processing candidate information...</>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Uploaded: {formatDate(file.uploaded_date)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {getStatusDescription(file.processing_status)}
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-3 flex-shrink-0">
                    {getStatusIcon(file.processing_status)}
                    
                    <div className="flex space-x-1">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleViewFile(file.cv_id, file.filename)}
                        title="View PDF"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDownloadFile(file.cv_id, file.filename)}
                        title="Download PDF"
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                      
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeleteFile(file.cv_id, file.filename)}
                        title="Delete CV"
                        className="hover:bg-red-50 hover:text-red-600 hover:border-red-200"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}