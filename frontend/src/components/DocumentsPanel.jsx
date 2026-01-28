import { useState, useEffect } from 'react';
import { documentAPI } from '../services/api';

export default function DocumentsPanel({ conversationId }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    loadDocuments();
  }, [conversationId]);
  
  const loadDocuments = async () => {
    try {
      const response = await documentAPI.list();
      setDocuments(response.data);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleDelete = async (id) => {
    if (!confirm('यो दस्तावेज मेटाउन चाहनुहुन्छ? (Delete this document?)')) {
      return;
    }
    
    try {
      await documentAPI.delete(id);
      setDocuments(documents.filter(doc => doc.id !== id));
    } catch (error) {
      console.error('Failed to delete document:', error);
    }
  };
  
  const getStatusBadge = (status) => {
    const badges = {
      pending: { text: 'प्रतीक्षारत', class: 'bg-yellow-100 text-yellow-800' },
      processing: { text: 'प्रक्रिया गर्दै', class: 'bg-blue-100 text-blue-800' },
      completed: { text: 'पूरा भयो', class: 'bg-green-100 text-green-800' },
      failed: { text: 'असफल', class: 'bg-red-100 text-red-800' },
    };
    
    const badge = badges[status] || badges.pending;
    
    return (
      <span className={`px-2 py-1 rounded text-xs font-medium ${badge.class}`}>
        {badge.text}
      </span>
    );
  };
  
  if (loading) {
    return (
      <div className="p-4 text-center text-gray-500">
        लोड गर्दै... (Loading...)
      </div>
    );
  }
  
  if (documents.length === 0) {
    return (
      <div className="p-4 text-center text-gray-500">
        <div className="text-4xl mb-2">📄</div>
        <p>कुनै दस्तावेज अपलोड गरिएको छैन</p>
        <p className="text-sm">No documents uploaded</p>
      </div>
    );
  }
  
  return (
    <div className="divide-y divide-gray-200">
      {documents.map((doc) => (
        <div key={doc.id} className="p-4 hover:bg-gray-50 transition">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-2xl">📄</span>
                <h3 className="font-medium text-gray-900 truncate">
                  {doc.filename}
                </h3>
              </div>
              
              <div className="flex items-center gap-2 mb-2">
                {getStatusBadge(doc.status)}
                {doc.num_pages && (
                  <span className="text-xs text-gray-500">
                    {doc.num_pages} pages
                  </span>
                )}
                {doc.num_chunks && (
                  <span className="text-xs text-gray-500">
                    {doc.num_chunks} chunks
                  </span>
                )}
              </div>
              
              {doc.error_message && (
                <p className="text-xs text-red-600 mt-1">{doc.error_message}</p>
              )}
              
              <p className="text-xs text-gray-400">
                {new Date(doc.created_at).toLocaleString()}
              </p>
            </div>
            
            <button
              onClick={() => handleDelete(doc.id)}
              className="text-red-600 hover:text-red-800 text-sm"
              title="Delete document"
            >
              🗑️
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}