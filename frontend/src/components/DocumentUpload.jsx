import { useState, useRef } from 'react';
import { documentAPI } from '../services/api';

export default function DocumentUpload({ conversationId, onUploadComplete }) {
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const [documentId, setDocumentId] = useState(null);
  const fileInputRef = useRef(null);
  
  const handleFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    // Validate file type
    if (!file.name.endsWith('.pdf')) {
      setError('कृपया PDF फाइल मात्र अपलोड गर्नुहोस् (Please upload PDF files only)');
      return;
    }
    
    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      setError('फाइल आकार 10MB भन्दा कम हुनुपर्छ (File size must be less than 10MB)');
      return;
    }
    
    setError('');
    setUploading(true);
    
    try {
      const response = await documentAPI.upload(file, conversationId);
      setDocumentId(response.data.id);
      setUploading(false);
      setProcessing(true);
      
      // Poll for processing status
      pollDocumentStatus(response.data.id);
      
    } catch (err) {
      console.error('Upload error:', err);
      setError('अपलोड असफल भयो। पुन: प्रयास गर्नुहोस्। (Upload failed. Please try again.)');
      setUploading(false);
    }
  };
  
  const pollDocumentStatus = async (docId) => {
    const maxAttempts = 60; // 5 minutes max
    let attempts = 0;
    
    const poll = async () => {
      try {
        const response = await documentAPI.get(docId);
        const status = response.data.status;
        
        if (status === 'completed') {
          setProcessing(false);
          if (onUploadComplete) {
            onUploadComplete(response.data);
          }
          return;
        }
        
        if (status === 'failed') {
          setProcessing(false);
          setError(response.data.error_message || 'प्रक्रिया असफल भयो (Processing failed)');
          return;
        }
        
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 5000); // Poll every 5 seconds
        } else {
          setProcessing(false);
          setError('प्रक्रिया समय समाप्त भयो (Processing timeout)');
        }
      } catch (err) {
        console.error('Polling error:', err);
        setProcessing(false);
      }
    };
    
    poll();
  };
  
  const handleClick = () => {
    fileInputRef.current?.click();
  };
  
  return (
    <div className="relative">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        onChange={handleFileSelect}
        className="hidden"
      />
      
      <button
        onClick={handleClick}
        disabled={uploading || processing}
        className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
        title="Upload PDF document"
      >
        {uploading || processing ? (
          <div className="flex items-center gap-2">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
                fill="none"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <span className="text-sm">
              {uploading ? 'अपलोड गर्दै...' : 'प्रक्रिया गर्दै...'}
            </span>
          </div>
        ) : (
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
            />
          </svg>
        )}
      </button>
      
      {error && (
        <div className="absolute top-full mt-2 left-0 right-0 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-sm">
          {error}
        </div>
      )}
      
      {processing && (
        <div className="absolute top-full mt-2 left-0 right-0 bg-blue-50 border border-blue-200 text-blue-700 px-3 py-2 rounded-lg text-sm">
          📄 कानुनी दस्तावेज प्रक्रिया गर्दै... कृपया प्रतीक्षा गर्नुहोस्।
          <br />
          <span className="text-xs">Processing legal document... Please wait.</span>
        </div>
      )}
    </div>
  );
}