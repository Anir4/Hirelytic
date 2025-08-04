const API_BASE_URL = 'http://localhost:8000';

// Get auth token from localStorage
const getAuthToken = () => {
  return localStorage.getItem('auth_token');
};

// Create headers with authentication
const createAuthHeaders = () => {
  const token = getAuthToken();
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` }),
  };
};

// Generic API request function
export const apiRequest = async (
  endpoint,
  options = {},
  responseType = 'json' // can be 'json', 'blob', 'text'
) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const config = {
    headers: createAuthHeaders(),
    ...options,
  };

  try {
    const response = await fetch(url, config);

    // Handle unauthorized access
    if (response.status === 401) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_data');
      window.location.href = '/';
      return null;
    }

    // Throw error if not ok
    if (!response.ok) {
      // Try to parse error from JSON if possible
      let errorData = null;
      try {
        errorData = await response.json();
      } catch (_) {
        // If it's a blob or text, do nothing
      }
      throw new Error(errorData?.detail || 'Request failed');
    }

    // Handle different response types
    switch (responseType) {
      case 'blob':
        return await response.blob();
      case 'text':
        return await response.text();
      case 'json':
      default:
        return await response.json();
    }
  } catch (error) {
    console.error(`API request failed for ${endpoint}:`, error);
    throw error;
  }
};


// Specific API functions
export const api = {
  // Auth endpoints
  auth: {
    login: (username, password) =>
      apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      }),
    
    register: (username, email, password) =>
      apiRequest('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ username, email, password }),
      }),
    
    getProfile: () => apiRequest('/auth/me'),
  },

  // CV management
  cvs: {
    getAll: (limit, search) => {
      const params = new URLSearchParams();
      if (limit) params.append('limit', limit);
      if (search) params.append('search', search);
      return apiRequest(`/api/files?${params}`);
    },

    upload: (file) => {
      const formData = new FormData();
      formData.append('file', file);
      return apiRequest('/api/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${getAuthToken()}` }, // Only auth header, no content-type for FormData
        body: formData,
      });
    },

    delete: (cvId) =>
      apiRequest(`/api/files/${cvId}`, { method: 'DELETE' }),
  },

  // Candidates
  candidates: {
    getAll: (limit, search) => {
      const params = new URLSearchParams();
      if (limit) params.append('limit', limit);
      if (search) params.append('search', search);
      return apiRequest(`/candidates?${params}`);
    },

    getDetail: (cvId) => apiRequest(`/candidates/${cvId}`),
  },

  files: {
  view: (cvId) =>
    apiRequest(`/api/files/view/${cvId}`, {}, 'blob'),

  download: (cvId) =>
    apiRequest(`/api/files/download/${cvId}`, {}, 'blob'),
  },

  // Chat/Query
  chat: {
    query: (question) => {
      const params = new URLSearchParams({ q: question });
      return apiRequest(`/query?${params}`);
    },

    getHistory: (limit) => {
      const params = new URLSearchParams();
      if (limit) params.append('limit', limit);
      return apiRequest(`/api/chats?${params}`);
    },
  },

  // Dashboard
  dashboard: {
    getStats: () => apiRequest('/api/dashboard/stats'),
    getRecent: () => apiRequest('/api/dashboard/recent'),
  },

  // Maintenance
  maintenance: {
    rebuildEmbeddings: () =>
      apiRequest('/api/maintenance/rebuild-embeddings', { method: 'POST' }),
  },
};

export default api;