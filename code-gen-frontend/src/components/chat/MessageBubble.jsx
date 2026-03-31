import CodeBlock from "./CodeBlock";

const parseContent = (text) => {
  const parts = [];
  const regex = /```(\w*)\n?([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", content: text.slice(lastIndex, match.index) });
    }
    parts.push({ type: "code", language: match[1] || "text", content: match[2].trim() });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push({ type: "text", content: text.slice(lastIndex) });
  }

  return parts;
};

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const parts = parseContent(message.content);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[85%] md:max-w-[75%] ${
          isUser
            ? "bg-dark text-bg-primary rounded-2xl rounded-br-md px-4 py-3"
            : "bg-bg-secondary text-dark rounded-2xl rounded-bl-md px-4 py-3"
        }`}
      >
        {message.files && message.files.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {message.files.map((file, i) => (
              <span
                key={i}
                className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md ${
                  isUser ? "bg-bg-primary/15" : "bg-dark/8"
                }`}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                {file.name}
              </span>
            ))}
          </div>
        )}

        {parts.map((part, i) =>
          part.type === "code" ? (
            <CodeBlock key={i} code={part.content} language={part.language} />
          ) : (
            <p key={i} className="text-sm leading-relaxed whitespace-pre-wrap">
              {part.content}
            </p>
          )
        )}
      </div>
    </div>
  );
}
