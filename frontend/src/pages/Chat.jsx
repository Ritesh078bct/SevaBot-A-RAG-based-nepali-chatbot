// import { useState, useEffect, useRef } from 'react';
// import { useNavigate } from 'react-router-dom';
// import { conversationAPI, authAPI } from '../services/api';

// export default function Chat() {
//   const navigate = useNavigate();
//   const messagesEndRef = useRef(null);
  
//   // State management
//   const [conversations, setConversations] = useState([]);
//   const [activeConversation, setActiveConversation] = useState(null);
//   const [messages, setMessages] = useState([]);
//   const [inputValue, setInputValue] = useState('');
//   const [loading, setLoading] = useState(false);
//   const [sidebarOpen, setSidebarOpen] = useState(true);
//   const [user, setUser] = useState(null);

//   // Load user data on mount
//   useEffect(() => {
//     const userData = localStorage.getItem('user');
//     if (userData) {
//       setUser(JSON.parse(userData));
//     }
//     loadConversations();
//   }, []);

//   // Auto-scroll to bottom when new messages arrive
//   useEffect(() => {
//     scrollToBottom();
//   }, [messages]);

//   const scrollToBottom = () => {
//     messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
//   };

//   // Load all conversations for sidebar
//   const loadConversations = async () => {
//     try {
//       const response = await conversationAPI.list();
//       setConversations(response.data);
//     } catch (error) {
//       console.error('Failed to load conversations:', error);
//     }
//   };

//   // Load specific conversation with messages
//   const loadConversation = async (id) => {
//     try {
//       const response = await conversationAPI.get(id);
//       setActiveConversation(response.data);
//       setMessages(response.data.messages);
//     } catch (error) {
//       console.error('Failed to load conversation:', error);
//     }
//   };

//   // Create new conversation
//   const startNewChat = async () => {
//     try {
//       const response = await conversationAPI.create({ title: 'New Chat' });
//       setConversations([response.data, ...conversations]);
//       setActiveConversation(response.data);
//       setMessages([]);
//     } catch (error) {
//       console.error('Failed to create conversation:', error);
//     }
//   };

//   // Send message
//   const handleSendMessage = async (e) => {
//     e.preventDefault();
//     if (!inputValue.trim() || loading) return;

//     // If no active conversation, create one
//     if (!activeConversation) {
//       await startNewChat();
//       // Wait for state to update
//       setTimeout(() => sendMessageToConversation(inputValue), 100);
//       return;
//     }

//     await sendMessageToConversation(inputValue);
//   };

//   const sendMessageToConversation = async (content) => {
//     setLoading(true);
//     const tempUserMessage = {
//       id: Date.now(),
//       role: 'user',
//       content: content,
//       created_at: new Date().toISOString(),
//     };

//     // Optimistic update - show user message immediately
//     setMessages([...messages, tempUserMessage]);
//     setInputValue('');

//     try {
//       const response = await conversationAPI.addMessage(activeConversation.id, content);
      
//       // Replace temp message with real messages from server
//       setMessages(prev => {
//         const withoutTemp = prev.filter(m => m.id !== tempUserMessage.id);
//         return [
//           ...withoutTemp,
//           response.data.user_message,
//           response.data.assistant_message,
//         ];
//       });

//       // Update conversation title if it's the first message
//       if (messages.length === 0) {
//         const updatedConv = {
//           ...activeConversation,
//           title: content.slice(0, 50),
//         };
//         await conversationAPI.update(activeConversation.id, updatedConv);
//         loadConversations(); // Refresh sidebar
//       }
//     } catch (error) {
//       console.error('Failed to send message:', error);
//       // Remove temp message on error
//       setMessages(prev => prev.filter(m => m.id !== tempUserMessage.id));
//     } finally {
//       setLoading(false);
//     }
//   };

//   // Logout handler
//   const handleLogout = async () => {
//     try {
//       await authAPI.logout();
//     } catch (error) {
//       console.error('Logout error:', error);
//     } finally {
//       localStorage.removeItem('token');
//       localStorage.removeItem('user');
//       navigate('/login');
//     }
//   };

//   return (
//     <div className="flex h-screen bg-gray-50">
//       {/* Sidebar */}
//       <div
//         className={`${
//           sidebarOpen ? 'w-80' : 'w-0'
//         } bg-gray-900 text-white transition-all duration-300 flex flex-col overflow-hidden`}
//       >
//         {/* Sidebar Header */}
//         <div className="p-4 border-b border-gray-700">
//           <div className="flex items-center justify-between mb-4">
//             <h2 className="text-xl font-bold">Chats</h2>
//             <button
//               onClick={() => setSidebarOpen(false)}
//               className="lg:hidden text-gray-400 hover:text-white"
//             >
//               ✕
//             </button>
//           </div>
//           <button
//             onClick={startNewChat}
//             className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg transition flex items-center justify-center gap-2"
//           >
//             <span className="text-xl">+</span>
//             New Chat
//           </button>
//         </div>

//         {/* Conversation List */}
//         <div className="flex-1 overflow-y-auto">
//           {conversations.map((conv) => (
//             <button
//               key={conv.id}
//               onClick={() => loadConversation(conv.id)}
//               className={`w-full p-4 text-left hover:bg-gray-800 transition border-b border-gray-800 ${
//                 activeConversation?.id === conv.id ? 'bg-gray-800' : ''
//               }`}
//             >
//               <div className="font-medium truncate">{conv.title}</div>
//               <div className="text-sm text-gray-400 truncate mt-1">
//                 {conv.last_message?.content || 'No messages yet'}
//               </div>
//               <div className="text-xs text-gray-500 mt-1">
//                 {new Date(conv.updated_at).toLocaleDateString()}
//               </div>
//             </button>
//           ))}
//         </div>

//         {/* User Section */}
//         <div className="p-4 border-t border-gray-700">
//           <div className="flex items-center justify-between">
//             <div className="flex items-center gap-3">
//               <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center font-bold">
//                 {user?.username?.charAt(0).toUpperCase()}
//               </div>
//               <div>
//                 <div className="font-medium">{user?.username}</div>
//                 <div className="text-xs text-gray-400">{user?.email}</div>
//               </div>
//             </div>
//             <button
//               onClick={handleLogout}
//               className="text-white hover:text-red-400 transition"
//               title="Logout"
//             >
//               signout
//             </button>
//           </div>
//         </div>
//       </div>

//       {/* Main Chat Area */}
//       <div className="flex-1 flex flex-col">
//         {/* Top Bar */}
//         <div className="bg-white border-b border-gray-200 p-4 flex items-center gap-4">
//           {!sidebarOpen && (
//             <button
//               onClick={() => setSidebarOpen(true)}
//               className="text-gray-600 hover:text-gray-900"
//             >
//               ☰
//             </button>
//           )}
//           <h1 className="text-xl font-semibold text-gray-800">
//             {activeConversation?.title || 'Select a chat or start a new one'}
//           </h1>
//         </div>

//         {/* Messages Area */}
//         <div className="flex-1 overflow-y-auto p-6">
//           {messages.length === 0 ? (
//             <div className="h-full flex items-center justify-center">
//               <div className="text-center text-gray-500">
//                 <div className="text-6xl mb-4">💬</div>
//                 <h2 className="text-2xl font-semibold mb-2">Start a conversation</h2>
//                 <p>Send a message to begin chatting</p>
//               </div>
//             </div>
//           ) : (
//             <div className="max-w-4xl mx-auto space-y-6">
//               {messages.map((message) => (
//                 <div
//                   key={message.id}
//                   className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
//                 >
//                   <div
//                     className={`max-w-[80%] rounded-2xl px-6 py-4 ${
//                       message.role === 'user'
//                         ? 'bg-blue-600 text-white'
//                         : 'bg-white border border-gray-200 text-gray-800'
//                     }`}
//                   >
//                     <div className="whitespace-pre-wrap">{message.content}</div>
//                     <div
//                       className={`text-xs mt-2 ${
//                         message.role === 'user' ? 'text-blue-100' : 'text-gray-400'
//                       }`}
//                     >
//                       {new Date(message.created_at).toLocaleTimeString()}
//                     </div>
//                   </div>
//                 </div>
//               ))}
//               <div ref={messagesEndRef} />
//             </div>
//           )}
//         </div>

//         {/* Input Area */}
//         <div className="border-t border-gray-200 bg-white p-4">
//           <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto">
//             <div className="flex gap-4 items-end">
//               <div className="flex-1 relative">
//                 <textarea
//                   value={inputValue}
//                   onChange={(e) => setInputValue(e.target.value)}
//                   onKeyDown={(e) => {
//                     if (e.key === 'Enter' && !e.shiftKey) {
//                       e.preventDefault();
//                       handleSendMessage(e);
//                     }
//                   }}
//                   placeholder="Type your message... (Shift+Enter for new line)"
//                   className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
//                   rows="3"
//                   disabled={loading}
//                 />
//               </div>
//               <button
//                 type="submit"
//                 disabled={loading || !inputValue.trim()}
//                 className="bg-blue-600 text-white px-6 py-3 rounded-xl font-semibold hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed h-fit"
//               >
//                 {loading ? 'Sending...' : 'Send'}
//               </button>
//             </div>
//           </form>
//         </div>
//       </div>
//     </div>
//   );
// }



import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { conversationAPI, authAPI } from '../services/api';
import DocumentUpload from '../components/DocumentUpload';
import DocumentsPanel from '../components/DocumentsPanel';

export default function Chat() {
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);
  
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showDocuments, setShowDocuments] = useState(false);
  const [user, setUser] = useState(null);

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
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const startNewChat = async () => {
    try {
      const response = await conversationAPI.create({ title: 'New Chat' });
      setConversations([response.data, ...conversations]);
      setActiveConversation(response.data);
      setMessages([]);
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
      const response = await conversationAPI.addMessage(
        activeConversation.id, 
        content,
        true // use_rag enabled
      );
      
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
      alert('Failed to send message. Check console for details.');
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
    console.log('Document uploaded:', document);
    // Optionally show a success message
    alert(`दस्तावेज सफलतापूर्वक प्रक्रिया भयो! (Document processed successfully!) 
${document.num_chunks} chunks created.`);
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div
        className={`${
          sidebarOpen ? 'w-80' : 'w-0'
        } bg-gray-900 text-white transition-all duration-300 flex flex-col overflow-hidden`}
      >
        {/* Sidebar Header */}
        <div className="p-4 border-b border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">
              {showDocuments ? 'Documents' : 'Chats'}
            </h2>
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden text-gray-400 hover:text-white"
            >
              ✕
            </button>
          </div>
          
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setShowDocuments(false)}
              className={`flex-1 py-2 px-3 rounded-lg transition ${
                !showDocuments 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
              }`}
            >
              💬 Chats
            </button>
            <button
              onClick={() => setShowDocuments(true)}
              className={`flex-1 py-2 px-3 rounded-lg transition ${
                showDocuments 
                  ? 'bg-blue-600 text-white' 
                  : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
              }`}
            >
              📄 Docs
            </button>
          </div>
          
          {!showDocuments && (
            <button
              onClick={startNewChat}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg transition flex items-center justify-center gap-2"
            >
              <span className="text-xl">+</span>
              New Chat
            </button>
          )}
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto">
          {showDocuments ? (
            <DocumentsPanel conversationId={activeConversation?.id} />
          ) : (
            <>
              {conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => loadConversation(conv.id)}
                  className={`w-full p-4 text-left hover:bg-gray-800 transition border-b border-gray-800 ${
                    activeConversation?.id === conv.id ? 'bg-gray-800' : ''
                  }`}
                >
                  <div className="font-medium truncate">{conv.title}</div>
                  <div className="text-sm text-gray-400 truncate mt-1">
                    {conv.last_message?.content || 'No messages yet'}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {new Date(conv.updated_at).toLocaleDateString()}
                  </div>
                </button>
              ))}
            </>
          )}
        </div>

        {/* User Section */}
        <div className="p-4 border-t border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center font-bold">
                {user?.username?.charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="font-medium">{user?.username}</div>
                <div className="text-xs text-gray-400">{user?.email}</div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="text-gray-400 hover:text-white transition"
              title="Logout"
            >
              🚪
            </button>
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Top Bar */}
        <div className="bg-white border-b border-gray-200 p-4 flex items-center gap-4">
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="text-gray-600 hover:text-gray-900"
            >
              ☰
            </button>
          )}
          <h1 className="text-xl font-semibold text-gray-800">
            {activeConversation?.title || 'नेपाली कानुनी सहायक (Nepali Legal Assistant)'}
          </h1>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6">
          {messages.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center text-gray-500 max-w-2xl">
                <div className="text-6xl mb-4">⚖️</div>
                <h2 className="text-2xl font-semibold mb-2">
                  नेपाली कानुनी सहायक
                </h2>
                <p className="mb-4">Nepali Legal Assistant with RAG</p>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-left text-sm">
                  <p className="font-semibold mb-2">कसरी प्रयोग गर्ने:</p>
                  <ol className="list-decimal list-inside space-y-1">
                    <li>पहिले कानुनी दस्तावेज (PDF) अपलोड गर्नुहोस्</li>
                    <li>दस्तावेज प्रक्रिया नभएसम्म प्रतीक्षा गर्नुहोस्</li>
                    <li>आफ्नो प्रश्न नेपालीमा सोध्नुहोस्</li>
                  </ol>
                  <p className="mt-3 text-xs text-gray-600">
                    The assistant will answer based only on uploaded documents.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto space-y-6">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-6 py-4 ${
                      message.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-white border border-gray-200 text-gray-800'
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{message.content}</div>
                    <div
                      className={`text-xs mt-2 ${
                        message.role === 'user' ? 'text-blue-100' : 'text-gray-400'
                      }`}
                    >
                      {new Date(message.created_at).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area with Document Upload */}
        <div className="border-t border-gray-200 bg-white p-4">
          <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto">
            <div className="flex gap-2 items-end">
              {/* Document Upload Button */}
              <DocumentUpload
                conversationId={activeConversation?.id}
                onUploadComplete={handleDocumentUploadComplete}
              />
              
              {/* Text Input */}
              <div className="flex-1 relative">
                <textarea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage(e);
                    }
                  }}
                  placeholder="आफ्नो प्रश्न नेपालीमा सोध्नुहोस्... (Ask your question in Nepali...)"
                  className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                  rows="3"
                  disabled={loading}
                />
              </div>
              
              {/* Send Button */}
              <button
                type="submit"
                disabled={loading || !inputValue.trim()}
                className="bg-blue-600 text-white px-6 py-3 rounded-xl font-semibold hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed h-fit"
              >
                {loading ? 'Sending...' : 'Send'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}