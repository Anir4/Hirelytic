import { useState, useEffect, useRef } from "react"
import { Send, Mic, MoreHorizontal, Download, Trash2, AlertCircle, User, Bot, FileText } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import { api } from "@/utils/api"

interface Message {
  id: string
  content: string
  role: "user" | "assistant"
  timestamp: string
  query_type?: "cv_search" | "general_chat"
  results?: any[]
  total_matches?: number
  error?: boolean
}

interface ChatHistory {
  id: number
  query: string
  query_type: string
  response_text: string
  cv_results: any
  created_at: string
}

export default function AskAI() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState("")
  const [isTyping, setIsTyping] = useState(false)
  const [error, setError] = useState<string>("")
  const [chatHistory, setChatHistory] = useState<ChatHistory[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Load chat history and convert to messages on component mount
  useEffect(() => {
    loadChatHistoryAndMessages()
  }, [])

  // Auto scroll to bottom when new messages arrive
  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  const loadChatHistoryAndMessages = async () => {
    setIsLoadingHistory(true)
    try {
      const data = await api.chat.getHistory(50) // Get more history to load all messages
      setChatHistory(data.chats || [])
      
      // Convert chat history to messages format
      if (data.chats && data.chats.length > 0) {
        const convertedMessages: Message[] = []
        
        // Sort chats by created_at to maintain chronological order
        const sortedChats = [...data.chats].sort((a, b) => 
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        )
        
        sortedChats.forEach((chat) => {
          // Add user message
          convertedMessages.push({
            id: `user-${chat.id}`,
            content: chat.query,
            role: "user",
            timestamp: new Date(chat.created_at).toLocaleTimeString([], { 
              hour: '2-digit', 
              minute: '2-digit' 
            }),
          })
          
          // Add assistant response
          convertedMessages.push({
            id: `assistant-${chat.id}`,
            content: chat.response_text,
            role: "assistant",
            timestamp: new Date(chat.created_at).toLocaleTimeString([], { 
              hour: '2-digit', 
              minute: '2-digit' 
            }),
            query_type: chat.query_type as "cv_search" | "general_chat",
            results: Array.isArray(chat.cv_results) ? chat.cv_results : (chat.cv_results?.results || []),
            total_matches: Array.isArray(chat.cv_results) ? chat.cv_results.length : (chat.cv_results?.total_matches || 0),
          })
        })
        setMessages(convertedMessages)
      }
    } catch (error) {
      console.error("Failed to load chat history:", error)
      // Don't show error for this, it's not critical
    } finally {
      setIsLoadingHistory(false)
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

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue.trim(),
      role: "user",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMessage])
    const currentQuery = inputValue.trim()
    setInputValue("")
    setIsTyping(true)
    setError("")

    try {
      const data = await api.chat.query(currentQuery)

      if (data) {
        const aiResponse: Message = {
          id: (Date.now() + 1).toString(),
          content: data.response_text || "I couldn't find an answer to your question.",
          role: "assistant",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          query_type: data.query_type,
          results: data.results || [],
          total_matches: data.total_matches || 0,
        }

        setMessages((prev) => [...prev, aiResponse])
        
        // Refresh chat history to include the new query
        await loadChatHistoryAndMessages()
      } else {
        throw new Error("No response received")
      }
    } catch (error) {
      console.error("Chat error:", error)
      
      const errorMessage: Message = {
        id: (Date.now() + 2).toString(),
        content: `❌ Failed to process your question: ${error.message || 'Please try again later.'}`,
        role: "assistant",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        error: true,
      }

      setMessages((prev) => [...prev, errorMessage])
      setError(error.message || "Failed to send message. Please try again.")
    } finally {
      setIsTyping(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const clearChat = () => {
    setMessages([])
    setError("")
  }

  const exportChat = () => {
    const chatData = messages.map(msg => ({
      role: msg.role,
      content: msg.content,
      timestamp: msg.timestamp,
      query_type: msg.query_type,
      total_matches: msg.total_matches
    }))

    const dataStr = JSON.stringify(chatData, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    
    const link = document.createElement('a')
    link.href = url
    link.download = `chat-export-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const formatContent = (content: string) => {
    // Simple markdown-like formatting for bold text
    return content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  }

  const renderCVResults = (results: any[], total_matches: number) => {
    if (!results || results.length === 0) return null

    return (
      <div className="mt-3 space-y-2">
        <div className="text-xs text-muted-foreground">
          Found {total_matches} matching CV{total_matches !== 1 ? 's' : ''}
        </div>
        <div className="space-y-2">
          {results.slice(0, 3).map((result, index) => (
            <div key={index} className="border rounded-lg p-3 bg-background/50">
              <div className="flex items-center justify-between mb-2">
                <div className="font-medium text-sm">
                  {result.candidate_name || 'Unknown Candidate'}
                </div>
                <Badge variant="outline" className="text-xs">
                  Rank #{index + 1}
                </Badge>
              </div>
              <button
                onClick={() => handleViewFile(result.cv_id, result.filename)}
                className="text-xs text-blue-600 hover:text-blue-800 hover:underline cursor-pointer mb-1 text-left"
                title="Click to view CV"
              >
                {result.filename}
              </button>
              {result.skills && result.skills.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {result.skills.slice(0, 5).map((skill: string, skillIndex: number) => (
                    <Badge key={skillIndex} variant="secondary" className="text-xs">
                      {skill}
                    </Badge>
                  ))}
                  {result.skills.length > 5 && (
                    <Badge variant="outline" className="text-xs">
                      +{result.skills.length - 5} more
                    </Badge>
                  )}
                </div>
              )}
            </div>
          ))}
          {results.length > 3 && (
            <div className="text-xs text-muted-foreground text-center py-2">
              ... and {results.length - 3} more results
            </div>
          )}
        </div>
      </div>
    )
  }

  const suggestedQuestions = [
    "Find candidates with Python experience",
    "Show me software engineers with 5+ years experience", 
    "Who has machine learning skills?",
    "Find candidates with leadership experience",
    "Show me recent graduates in computer science",
    "Who has worked at startup companies?"
  ]

  const handleSuggestionClick = (suggestion: string) => {
    setInputValue(suggestion)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Ask AI</h1>
          <p className="text-muted-foreground">
            Ask questions about your candidates and get intelligent insights
          </p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="icon">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="bg-popover">
            <DropdownMenuItem onClick={exportChat} disabled={messages.length === 0}>
              <Download className="mr-2 h-4 w-4" />
              Export Chat
            </DropdownMenuItem>
            <DropdownMenuItem onClick={clearChat} disabled={messages.length === 0}>
              <Trash2 className="mr-2 h-4 w-4" />
              Clear Chat
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert className="mb-4 border-red-200 bg-red-50">
          <AlertCircle className="h-4 w-4 text-red-600" />
          <AlertDescription className="text-red-800">{error}</AlertDescription>
        </Alert>
      )}

      {/* Chat Container */}
      <Card className="flex-1 flex flex-col">
        <CardContent className="flex-1 flex flex-col p-0">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {isLoadingHistory ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <Bot className="mx-auto h-12 w-12 text-muted-foreground mb-4 animate-pulse" />
                  <p className="text-muted-foreground">Loading chat history...</p>
                </div>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center max-w-md">
                  <Bot className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium mb-2">Start a conversation</h3>
                  <p className="text-muted-foreground mb-6">
                    Ask questions about your candidates to get AI-powered insights
                  </p>
                  
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-muted-foreground">Try asking:</p>
                    <div className="grid gap-2">
                      {suggestedQuestions.map((question, index) => (
                        <Button
                          key={index}
                          variant="outline"
                          size="sm"
                          className="text-left justify-start h-auto py-2 px-3 whitespace-normal"
                          onClick={() => handleSuggestionClick(question)}
                        >
                          "{question}"
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <>
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={cn(
                      "flex w-full",
                      message.role === "user" ? "justify-end" : "justify-start"
                    )}
                  >
                    <div
                      className={cn(
                        "max-w-[85%] rounded-lg px-4 py-3",
                        message.role === "user"
                          ? "bg-primary ml-4"
                          : message.error
                          ? "bg-red-50 border border-red-200 mr-4"
                          : "bg-muted mr-4"
                      )}
                    >
                      <div className="flex items-start space-x-2 mb-2">
                        {message.role === "user" ? (
                          <User className="h-4 w-4 mt-0.5 flex-shrink-0" />
                        ) : (
                          <Bot className="h-4 w-4 mt-0.5 flex-shrink-0" />
                        )}
                        <div className="text-xs font-medium opacity-70">
                          {message.role === "user" ? "You" : "AI Assistant"}
                        </div>
                      </div>
                      
                      <div 
                        className="whitespace-pre-wrap text-sm leading-relaxed"
                        dangerouslySetInnerHTML={{ __html: formatContent(message.content) }}
                      />
                      
                      {/* CV Search Results */}
                      {message.query_type === "cv_search" && message.results && (
                        renderCVResults(message.results, message.total_matches || 0)
                      )}
                      
                      {/* Query Type Badge */}
                      <div className="flex items-center justify-between mt-3">
                        <div className="text-xs opacity-70">
                          {message.timestamp}
                        </div>
                        {message.query_type && (
                          <Badge variant="outline" className="text-xs">
                            {message.query_type === "cv_search" ? (
                              <>
                                <FileText className="w-3 h-3 mr-1" />
                                CV Search
                              </>
                            ) : (
                              "General Chat"
                            )}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                
                {isTyping && (
                  <div className="flex justify-start">
                    <div className="bg-muted rounded-lg px-4 py-3 mr-4">
                      <div className="flex items-center space-x-2">
                        <Bot className="h-4 w-4 text-muted-foreground" />
                        <div className="flex space-x-1">
                          <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:-0.3s]" />
                          <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:-0.15s]" />
                          <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Input Area */}
          <div className="p-4 border-t border-border">
            <div className="flex space-x-2">
              <Input
                placeholder="Ask anything about your candidates..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                className="flex-1"
                disabled={isTyping || isLoadingHistory}
              />
              <Button 
                onClick={handleSendMessage} 
                disabled={!inputValue.trim() || isTyping || isLoadingHistory}
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <div className="text-xs text-muted-foreground mt-2">
              Press Enter to send, Shift+Enter for new line
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}