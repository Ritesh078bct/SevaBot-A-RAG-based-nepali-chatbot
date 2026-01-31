import { useState } from 'react';
import DocumentsPanel from './DocumentsPanel';

export default function Sidebar({
  conversations,
  activeConversation,
  user,
  sidebarOpen,
  setSidebarOpen,
  onSelectConversation,
  onNewChat,
  onLogout,
  onDeleteConversation,
}) {
  const [showDocuments, setShowDocuments] = useState(false);

  return (
    <>
      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar - Hidden on mobile unless open, always visible on desktop */}
      <div
        className={`
          fixed md:static inset-y-0 left-0 z-50
          w-80 bg-gradient-to-b from-gray-900 to-gray-800 text-white
          transform transition-transform duration-300 ease-in-out
          md:transform-none
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          md:translate-x-0
          flex flex-col shadow-2xl
        `}
      >
        {/* Sidebar Header */}
        <div className="p-4 md:p-6 border-b border-gray-700 flex-shrink-0">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl md:text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                SevaBot
              </h2>
              <p className="text-xs text-gray-400 mt-1">
                RAG-Based Assistant
              </p>
            </div>
            {/* Close button - Only visible on mobile */}
            <button
              onClick={() => setSidebarOpen(false)}
              className="md:hidden text-gray-400 hover:text-white transition p-1"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Tab Switcher */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setShowDocuments(false)}
              className={`flex-1 py-2 px-3 rounded-lg transition font-medium text-sm ${!showDocuments
                ? 'bg-blue-600 text-white shadow-lg'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
            >
              💬 कुराकानी
            </button>
            <button
              onClick={() => setShowDocuments(true)}
              className={`flex-1 py-2 px-3 rounded-lg transition font-medium text-sm ${showDocuments
                ? 'bg-blue-600 text-white shadow-lg'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
            >
              📄 दस्तावेज
            </button>
          </div>

          {/* New Chat Button */}
          {!showDocuments && (
            <button
              onClick={onNewChat}
              className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white py-2.5 md:py-3 px-4 rounded-xl transition flex items-center justify-center gap-2 shadow-lg font-medium text-sm md:text-base"
            >
              <span className="text-xl">+</span>
              नयाँ कुराकानी
            </button>
          )}
        </div>

        {/* Content Area - Scrollable */}
        <div className="flex-1 overflow-y-auto">
          {showDocuments ? (
            <DocumentsPanel conversationId={activeConversation?.id} />
          ) : (
            <div className="p-2">
              {conversations.length === 0 ? (
                <div className="text-center text-gray-400 py-8 px-4 text-sm">
                  कुनै कुराकानी छैन। नयाँ सुरु गर्नुहोस्!
                </div>
              ) : (
                conversations.map((conv) => (
                  <div
                    key={conv.id}
                    className={`group relative w-full p-3 md:p-4 hover:bg-gray-700 transition rounded-lg mb-2 ${activeConversation?.id === conv.id
                      ? 'bg-gray-700 border-l-4 border-blue-500'
                      : ''
                      }`}
                  >
                    <button
                      onClick={() => onSelectConversation(conv.id)}
                      className="w-full text-left"
                    >
                      <div className="font-medium truncate text-sm md:text-base pr-8">
                        {conv.title}
                      </div>
                      <div className="text-xs md:text-sm text-gray-400 truncate mt-1">
                        {conv.last_message?.content || 'कुनै सन्देश छैन'}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        {new Date(conv.updated_at).toLocaleDateString('ne-NP')}
                      </div>
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteConversation(conv.id);
                      }}
                      className="absolute top-3 right-3 p-1.5 opacity-0 group-hover:opacity-100 hover:bg-red-600 rounded transition"
                      title="मेटाउनुहोस्"
                    >
                      <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* User Section with Beautified Logout */}
        <div className="p-4 border-t border-gray-700 bg-gray-900 flex-shrink-0">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center font-bold text-base md:text-lg flex-shrink-0">
              {user?.username?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="min-w-0 flex-1">
              <div className="font-medium truncate text-sm md:text-base">
                {user?.username || 'User'}
              </div>
              <div className="text-xs text-gray-400 truncate">
                {user?.email || 'user@example.com'}
              </div>
            </div>
          </div>

          {/* Beautified Logout Button */}
          <button
            onClick={onLogout}
            className="w-full py-2.5 px-4 rounded-lg border-2 border-red-500/30 bg-red-500/5 text-red-400 hover:bg-red-500/20 hover:border-red-500 transition font-medium text-sm flex items-center justify-center gap-2 group"
          >
            <svg
              className="w-5 h-5 group-hover:translate-x-1 transition-transform"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
              />
            </svg>
            <span>बाहिर निस्कनुहोस्</span>
          </button>
        </div>
      </div>
    </>
  );
}