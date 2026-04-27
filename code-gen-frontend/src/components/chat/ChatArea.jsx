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
  // id-ul unei conversatii create local: sarim peste fetch ca sa nu suprascriem state-ul curent
  const skipNextFetchRef = useRef(null);

  useEffect(() => {
    if (!conversationId) { setMessages([]); return; }
    if (skipNextFetchRef.current === conversationId) {
      skipNextFetchRef.current = null;
      return;
    }
    conversationService.getMessages(conversationId).then(setMessages);
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text, files) => {
    if (!text) return;

    // PASUL 1: asigura conversatia — creata lazy la primul mesaj
    let activeId = conversationId;
    if (!activeId) {
      const conv = await conversationService.create(text.slice(0, 50));
      activeId = conv.id;
      // marcam id-ul ca "detinut local" inainte de navigate, ca effect-ul sa nu refetcheze
      skipNextFetchRef.current = activeId;
      onConversationUpdate(activeId);
    }

    // PASUL 2: salveaza mesajul user pe server (sursa de adevar)
    let savedUserMsg;
    try {
      savedUserMsg = await conversationService.addMessage(activeId, "user", text);
    } catch {
      return;
    }

    // PASUL 3: update UI optimist — mesajul user + placeholder pentru assistant
    const updatedMessages = [
      ...messages,
      savedUserMsg,
      { id: crypto.randomUUID(), role: "assistant", content: "", created_at: new Date().toISOString() },
    ];
    setMessages(updatedMessages);
    setIsStreaming(true);

    // PASUL 4: stream de la Chat Service cu tot istoricul (fara placeholder-ul gol)
    let fullResponse = "";
    const messagesForModel = updatedMessages.slice(0, -1);

    try {
      await generateService.streamCode(messagesForModel, (chunk) => {
        fullResponse += chunk;
        setMessages((prev) => {
          const copy = [...prev];
          copy[copy.length - 1] = { ...copy[copy.length - 1], content: fullResponse };
          return copy;
        });
      });
    } catch (err) {
      fullResponse += `\n\n[Eroare: ${err.message}]`;
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = { ...copy[copy.length - 1], content: fullResponse };
        return copy;
      });
    } finally {
      setIsStreaming(false);
      // PASUL 5: persista raspunsul (chiar si partial daca streaming a esuat)
      if (fullResponse) {
        try {
          await conversationService.addMessage(activeId, "assistant", fullResponse);
        } catch {
          // raspunsul e afisat dar nesalvat in istoric
        }
      }
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
