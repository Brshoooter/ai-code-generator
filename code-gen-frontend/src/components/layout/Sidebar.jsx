import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { conversationService } from "../../services/conversationService";

export default function Sidebar({ conversations, onNewConversation, onRefresh, isOpen, onToggle }) {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleNew = () => {
    const conversation = onNewConversation();
    navigate(`/chat/${conversation.id}`);
  };

  const handleSelect = (id) => {
    navigate(`/chat/${id}`);
    if (window.innerWidth < 768) onToggle();
  };

  const handleDelete = (e, id) => {
    e.stopPropagation();
    conversationService.delete(id);
    onRefresh();
    if (conversationId === id) navigate("/");
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-20 md:hidden"
          onClick={onToggle}
        />
      )}

      <aside
        className={`fixed md:static z-30 top-0 left-0 h-full w-64 bg-dark flex flex-col transition-transform duration-200 ${
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="p-4 flex items-center justify-between">
          <h1 className="text-bg-primary text-lg font-semibold tracking-tight">CodeGen</h1>
          <button
            onClick={onToggle}
            className="text-inactive hover:text-bg-primary md:hidden cursor-pointer"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-3 mb-2">
          <button
            onClick={handleNew}
            className="w-full py-2.5 px-3 rounded-lg border border-bg-primary/20 text-bg-primary/80 text-sm hover:bg-bg-primary/10 transition-colors cursor-pointer flex items-center gap-2"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12h14" />
            </svg>
            New Conversation
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-1">
          {conversations.length === 0 && (
            <p className="text-inactive/60 text-xs text-center mt-8">No conversations yet</p>
          )}
          {conversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => handleSelect(conv.id)}
              className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg mb-0.5 cursor-pointer text-sm transition-colors ${
                conversationId === conv.id
                  ? "bg-bg-primary/15 text-bg-primary"
                  : "text-inactive hover:bg-bg-primary/8 hover:text-bg-primary/90"
              }`}
            >
              <span className="flex-1 truncate">{conv.title}</span>
              <button
                onClick={(e) => handleDelete(e, conv.id)}
                className="opacity-0 group-hover:opacity-100 text-inactive hover:text-error transition-opacity cursor-pointer shrink-0"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>

        <div className="p-3 border-t border-bg-primary/10">
          <div className="flex items-center justify-between px-2">
            <span className="text-inactive text-xs truncate">{user?.email}</span>
            <button
              onClick={handleLogout}
              className="text-inactive hover:text-bg-primary text-xs cursor-pointer"
            >
              Logout
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
