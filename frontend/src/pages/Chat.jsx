import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { conversationAPI, authAPI, messageAPI } from '../services/api';
import Sidebar from '.././components/Sidebar';
import DocumentUpload from '.././components/DocumentUpload';

export default function Chat() {
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);

  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [user, setUser] = useState(null);
  const [editingMessageId, setEditingMessageId] = useState(null);
  const [editContent, setEditContent] = useState('');

  useEffect(() => {
    const userData = localStorage.getItem('user');
    if (userData) {
      setUser(JSON.parse(userData));
    }
    loadConversations();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadConversations = async () => {
    try {
      const response = await conversationAPI.list();
      setConversations(response.data);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const response = await conversationAPI.get(id);
      setActiveConversation(response.data);
      setMessages(response.data.messages);
      setSidebarOpen(false); // Close sidebar on mobile after selection
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const startNewChat = async () => {
    try {
      const response = await conversationAPI.create({ title: 'नयाँ कुराकानी' });
      setConversations([response.data, ...conversations]);
      setActiveConversation(response.data);
      setMessages([]);
      setSidebarOpen(false); // Close sidebar on mobile
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || loading) return;

    if (!activeConversation) {
      await startNewChat();
      setTimeout(() => sendMessageToConversation(inputValue), 100);
      return;
    }

    await sendMessageToConversation(inputValue);
  };

  const sendMessageToConversation = async (content) => {
    setLoading(true);
    const tempUserMessage = {
      id: Date.now(),
      role: 'user',
      content: content,
      created_at: new Date().toISOString(),
    };

    setMessages([...messages, tempUserMessage]);
    setInputValue('');

    try {
      const response = await conversationAPI.addMessage(activeConversation.id, content);

      setMessages(prev => {
        const withoutTemp = prev.filter(m => m.id !== tempUserMessage.id);
        return [
          ...withoutTemp,
          response.data.user_message,
          response.data.assistant_message,
        ];
      });

      if (messages.length === 0) {
        const updatedConv = {
          ...activeConversation,
          title: content.slice(0, 50),
        };
        await conversationAPI.update(activeConversation.id, updatedConv);
        loadConversations();
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      setMessages(prev => prev.filter(m => m.id !== tempUserMessage.id));
      alert('प्रश्न पठाउन असफल भयो। पुन: प्रयास गर्नुहोस्।');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      navigate('/login');
    }
  };

  const handleDocumentUploadComplete = (document) => {
    console.log('Document processed:', document);
    // Reload conversations to show updated document count
    loadConversations();
  };

  const handleDeleteMessage = async (messageId) => {
    if (!window.confirm('यो सन्देश मेटाउन निश्चित हुनुहुन्छ?')) return;

    try {
      await messageAPI.delete(messageId);
      setMessages(prev => prev.filter(m => m.id !== messageId));
    } catch (error) {
      console.error('Failed to delete message:', error);
      alert('सन्देश मेटाउन असफल भयो।');
    }
  };

  const handleStartEdit = (message) => {
    setEditingMessageId(message.id);
    setEditContent(message.content);
  };

  const handleCancelEdit = () => {
    setEditingMessageId(null);
    setEditContent('');
  };

  const handleSaveEdit = async (messageId) => {
    if (!editContent.trim()) return;

    setLoading(true);
    try {
      const response = await messageAPI.update(messageId, editContent);

      // Update messages: replace edited user message and add new assistant response
      setMessages(prev => {
        const filtered = prev.filter(m => m.id !== messageId);
        // Also remove old assistant response if it exists
        const userMsgIndex = prev.findIndex(m => m.id === messageId);
        if (userMsgIndex !== -1 && userMsgIndex + 1 < prev.length) {
          const nextMsg = prev[userMsgIndex + 1];
          if (nextMsg.role === 'assistant') {
            return [
              ...filtered.filter(m => m.id !== nextMsg.id),
              response.data.user_message,
              response.data.assistant_message
            ].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
          }
        }
        return [
          ...filtered,
          response.data.user_message,
          response.data.assistant_message
        ].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
      });

      setEditingMessageId(null);
      setEditContent('');
    } catch (error) {
      console.error('Failed to edit message:', error);
      alert('सन्देश सम्पादन असफल भयो।');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyMessage = async (content) => {
    try {
      await navigator.clipboard.writeText(content);
      // Silent copy - no alert
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  const handleDeleteConversation = async (conversationId) => {
    alert("Delete conversation");
    try {
      await conversationAPI.delete(conversationId);
      setConversations(prev => prev.filter(c => c.id !== conversationId));

      if (activeConversation?.id === conversationId) {
        setActiveConversation(null);
        setMessages([]);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      alert('कुराकानी मेटाउन असफल भयो।');
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Responsive Sidebar */}
      <Sidebar
        conversations={conversations}
        activeConversation={activeConversation}
        user={user}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        onSelectConversation={loadConversation}
        onNewChat={startNewChat}
        onLogout={handleLogout}
        onDeleteConversation={handleDeleteConversation}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header with Branding */}
        <div className="bg-white border-b border-gray-200 shadow-sm px-4 py-3 flex items-center gap-3 flex-shrink-0">
          {/* Hamburger Menu - Hidden on Desktop */}
          <button
            onClick={() => setSidebarOpen(true)}
            className="md:hidden p-2 hover:bg-gray-100 rounded-lg transition text-gray-600"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          {/* Branding */}
          <div className="flex-1">
            <h1 className="text-lg md:text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              SevaBot: A RAG Based Nepali Chatbot
            </h1>
            <p className="text-xs text-gray-500 hidden sm:block">
              नेपाली कानुनी सहायक | Retrieval-Augmented Generation System
            </p>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {messages.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center text-gray-600 max-w-2xl px-4">
                <div className="text-6xl md:text-7xl mb-4">⚖️</div>
                <h2 className="text-2xl md:text-3xl font-bold mb-3 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  नमस्कार! म SevaBot हुँ
                </h2>
                <p className="text-base md:text-lg mb-6">तपाईंको नेपाली कानुनी सहायक</p>

                <div className="bg-gradient-to-br from-blue-50 to-purple-50 border border-blue-200 rounded-2xl p-4 md:p-6 text-left shadow-lg">
                  <h3 className="font-bold text-base md:text-lg mb-4 text-blue-900">कसरी प्रयोग गर्ने:</h3>
                  <div className="space-y-3 text-sm md:text-base">
                    <div className="flex items-start gap-3">
                      <span className="text-xl md:text-2xl flex-shrink-0">📄</span>
                      <div>
                        <p className="font-semibold">१. दस्तावेज अपलोड गर्नुहोस्</p>
                        <p className="text-xs md:text-sm text-gray-600">तलको 📎 बटनमा क्लिक गरी PDF अपलोड गर्नुहोस्</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <span className="text-xl md:text-2xl flex-shrink-0">⏳</span>
                      <div>
                        <p className="font-semibold">२. प्रक्रिया पूरा हुन प्रतीक्षा गर्नुहोस्</p>
                        <p className="text-xs md:text-sm text-gray-600">दस्तावेज प्रक्रिया भएपछि प्रश्न सोध्न सक्नुहुन्छ</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <span className="text-xl md:text-2xl flex-shrink-0">💬</span>
                      <div>
                        <p className="font-semibold">३. नेपालीमा प्रश्न सोध्नुहोस्</p>
                        <p className="text-xs md:text-sm text-gray-600">म दस्तावेज र सामान्य ज्ञानको आधारमा उत्तर दिनेछु</p>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 p-3 bg-white rounded-lg border border-blue-200">
                    <p className="text-xs text-gray-600">
                      <strong>ध्यान दिनुहोस्:</strong> SevaBot ले स्थायी कानुनी ज्ञान र तपाईंले अपलोड गर्नुभएको दस्तावेज दुवैबाट जानकारी प्रदान गर्छ।
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto space-y-4 md:space-y-6">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] md:max-w-[80%] rounded-2xl px-4 py-3 md:px-6 md:py-4 shadow-md ${message.role === 'user'
                      ? 'bg-gradient-to-br from-blue-600 to-blue-700 text-white'
                      : 'bg-white border border-gray-200 text-gray-800'
                      }`}
                  >
                    {message.role === 'assistant' && (
                      <div className="flex items-center justify-between gap-2 mb-2 pb-2 border-b border-gray-200">
                        <div className="flex items-center gap-2">
                          <span className="text-lg md:text-xl">🤖</span>
                          <span className="font-semibold text-xs md:text-sm text-blue-600">SevaBot</span>
                        </div>
                        {/* Assistant message actions - Copy only */}
                        <button
                          onClick={() => handleCopyMessage(message.content)}
                          className="p-1.5 hover:bg-gray-100 rounded-lg transition"
                          title="प्रतिलिपि गर्नुहोस्"
                        >
                          <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                        </button>
                      </div>
                    )}

                    {/* Message content or edit mode */}
                    {editingMessageId === message.id ? (
                      <div className="space-y-3 bg-gray-50 p-4 rounded-lg border-2 border-blue-300">
                        <div className="text-xs font-semibold text-blue-700 mb-2">✏️ सम्पादन गर्दै</div>
                        <textarea
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          className="w-full p-3 border-2 border-gray-300 rounded-lg text-gray-800 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition"
                          rows="4"
                          autoFocus
                          placeholder="आफ्नो प्रश्न सम्पादन गर्नुहोस्..."
                        />
                        <div className="flex gap-2 justify-end">
                          <button
                            onClick={handleCancelEdit}
                            className="px-4 py-2 text-sm font-medium bg-white border-2 border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg transition"
                          >
                            रद्द गर्नुहोस्
                          </button>
                          <button
                            onClick={() => handleSaveEdit(message.id)}
                            disabled={loading}
                            className="px-4 py-2 text-sm font-medium bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed shadow-md"
                          >
                            {loading ? '⏳ पठाउँदै...' : '✓ सुरक्षित गर्नुहोस्'}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="whitespace-pre-wrap leading-relaxed text-sm md:text-base">
                          {message.content}
                        </div>
                        <div className="flex items-center justify-between mt-2">
                          <div
                            className={`text-xs ${message.role === 'user' ? 'text-blue-100' : 'text-gray-400'
                              }`}
                          >
                            {new Date(message.created_at).toLocaleTimeString('ne-NP')}
                          </div>

                          {/* User message actions - Edit only */}
                          {message.role === 'user' && (
                            <button
                              onClick={() => handleStartEdit(message)}
                              className="p-1.5 hover:bg-blue-800 rounded-lg transition"
                              title="सम्पादन गर्नुहोस्"
                            >
                              <svg className="w-4 h-4 text-blue-100" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                              </svg>
                            </button>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Gemini-Style Input Box */}
        <div className="border-t border-gray-200 bg-white px-4 py-4 flex-shrink-0">
          <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto">
            {/* Container with relative positioning */}
            <div className="relative">
              {/* Textarea with padding for buttons */}
              <textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage(e);
                  }
                }}
                placeholder="आफ्नो प्रश्न नेपालीमा सोध्नुहोस्..."
                className="w-full pl-12 pr-12 py-3 md:py-4 border-2 border-gray-300 rounded-2xl focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none hover:border-gray-400 transition text-sm md:text-base"
                rows="1"
                disabled={loading}
                style={{
                  minHeight: '52px',
                  maxHeight: '120px',
                  fontFamily: 'system-ui, -apple-system, sans-serif'
                }}
              />

              {/* Attachment Button - Bottom Left */}
              <div className="absolute bottom-3 left-3">
                <DocumentUpload
                  conversationId={activeConversation?.id}
                  onUploadComplete={handleDocumentUploadComplete}
                />
              </div>

              {/* Send Button - Bottom Right */}
              <button
                type="submit"
                disabled={loading || !inputValue.trim()}
                className="absolute bottom-3 right-3 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white p-2 md:p-2.5 rounded-xl transition disabled:opacity-50 disabled:cursor-not-allowed shadow-md hover:shadow-lg disabled:shadow-none"
                title="पठाउनुहोस्"
              >
                {loading ? (
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
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}