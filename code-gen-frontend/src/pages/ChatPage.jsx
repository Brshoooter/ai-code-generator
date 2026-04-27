import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/layout/Sidebar";
import ChatArea from "../components/chat/ChatArea";
import { conversationService } from "../services/conversationService";

export default function ChatPage() {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    conversationService.getAll()
      .then(setConversations)
      .finally(() => setLoading(false));
  }, []);

  const refreshConversations = useCallback(async () => {
    const data = await conversationService.getAll();
    setConversations(data);
  }, []);

  const handleConversationUpdate = useCallback(async (newId) => {
    if (newId) navigate(`/chat/${newId}`);
    await refreshConversations();
  }, [refreshConversations, navigate]);

  return (
    <div className="h-screen flex bg-bg-primary overflow-hidden">
      <Sidebar
        conversations={conversations}
        loading={loading}
        onRefresh={refreshConversations}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center gap-3 px-4 py-3 border-b border-border/20 md:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1 text-accent hover:text-dark cursor-pointer"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <span className="text-sm font-semibold text-dark">CodeGen</span>
        </header>

        <ChatArea onConversationUpdate={handleConversationUpdate} />
      </div>
    </div>
  );
}
