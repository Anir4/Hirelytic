import { useLocation } from "react-router-dom";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error(
      "404 Error: User attempted to access non-existent route:",
      location.pathname
    );
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background Image with Blur */}
      <div 
        className="absolute inset-0 bg-cover bg-center bg-no-repeat filter blur-md scale-110"
        style={{
            backgroundImage: "url('./Back.jpg')"
        }}
      ></div>
      
      {/* Dark overlay for better contrast */}
      <div className="absolute inset-0 bg-black/40"></div>
      
      {/* Optional: Additional blur overlay for extra effect */}
      <div className="absolute inset-0 backdrop-blur-sm"></div>

      <div className="relative z-10 w-full max-w-md">
        <Card className="backdrop-blur-lg bg-white/10 border-white/20 shadow-2xl">
          <CardContent className="text-center py-12 px-8">
            <div className="space-y-6">
              {/* 404 Number */}
              <h1 className="text-8xl font-bold text-white/90 drop-shadow-lg">
                404
              </h1>
              
              {/* Error Message */}
              <div className="space-y-2">
                <h2 className="text-2xl font-semibold text-white">
                  Oops! Page not found
                </h2>
                <p className="text-white/70 text-sm">
                  The page you're looking for doesn't exist or has been moved.
                </p>
              </div>
              
              {/* Action Buttons */}
              <div className="space-y-3 pt-4">
                <Button 
                  onClick={() => window.location.href = '/'}
                  className="w-full bg-white/20 hover:bg-white/30 text-white border border-white/30 hover:border-white/50 backdrop-blur-sm shadow-lg transition-all duration-200"
                >
                  Return to Home
                </Button>
                
                <Button 
                  onClick={() => window.history.back()}
                  variant="outline"
                  className="w-full bg-transparent hover:bg-white/10 text-white/80 border-white/30 hover:border-white/50 hover:text-white backdrop-blur-sm transition-all duration-200"
                >
                  Go Back
                </Button>
              </div>
              
              {/* Additional Info */}
              <div className="pt-4 border-t border-white/20">
                <p className="text-xs text-white/50">
                  Error code: 404 • Path: {location.pathname}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default NotFound;