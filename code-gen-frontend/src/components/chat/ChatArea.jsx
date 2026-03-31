import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import { generateService } from "../../services/generateService";
import { conversationService } from "../../services/conversationService";

export default function ChatArea({ onConversationUpdate }) {
  const { conversationId } = useParams();
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (conversationId) {
      const conversation = conversationService.getById(conversationId);
      setMessages(conversation?.messages || []);
    } else {
      setMessages([]);
    }
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text, files) => {
    if (!text && files.length === 0) return;

    let activeId = conversationId;

    if (!activeId) {
      const conversation = conversationService.create(text.slice(0, 50));
      activeId = conversation.id;
      onConversationUpdate(activeId);
    }

    const fileData = files.map((f) => ({ name: f.name, size: f.size }));

    conversationService.addMessage(activeId, "user", text, fileData);

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      files: fileData,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);

    const aiMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      files: [],
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, aiMessage]);
    setIsStreaming(true);

    let fullResponse = "";

    try {
      await generateService.streamCode(text, (chunk) => {
        fullResponse += chunk;
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = { ...updated[updated.length - 1], content: fullResponse };
          return updated;
        });
      });
    } catch (err) {
      fullResponse += `\n\n[Error: ${err.message}]`;
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { ...updated[updated.length - 1], content: fullResponse };
        return updated;
      });
    } finally {
      setIsStreaming(false);
      conversationService.addMessage(activeId, "assistant", fullResponse);
      onConversationUpdate(null);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full min-w-0">
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center">
            <div className="w-12 h-12 rounded-2xl bg-dark flex items-center justify-center mb-4">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#FAF9FA" strokeWidth="1.5">
                <polyline points="16 18 22 12 16 6" />
                <polyline points="8 6 2 12 8 18" />
                <line x1="14" y1="4" x2="10" y2="20" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-dark mb-1">What would you like to build?</h2>
            <p className="text-accent text-sm max-w-sm">
              Describe the code you need and I'll generate it for you in real time.
            </p>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isStreaming && (
              <div className="flex justify-start mb-4">
                <div className="flex items-center gap-1.5 px-3 py-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                  <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" style={{ animationDelay: "0.2s" }} />
                  <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" style={{ animationDelay: "0.4s" }} />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </>
        )}
      </div>

      <ChatInput onSend={handleSend} disabled={isStreaming} />
    </div>
  );
}
