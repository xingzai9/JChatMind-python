import React, { useState } from "react";
import { Sender } from "@ant-design/x";
import FileUploadButton from "./FileUploadButton";

interface AgentChatInputProps {
  onSend: (message: string, file?: File) => void;
  disabled?: boolean;
}

const AgentChatInput: React.FC<AgentChatInputProps> = ({ onSend, disabled = false }) => {
  const [message, setMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleFileSelected = (file: File) => {
    setSelectedFile(file);
  };

  const handleSubmit = () => {
    const trimmedMessage = message.trim();
    
    // 如果有文件，即使没有消息也可以发送
    if (trimmedMessage || selectedFile) {
      onSend(trimmedMessage || "请分析这个文件", selectedFile || undefined);
      setMessage("");
      setSelectedFile(null);
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
      <FileUploadButton onFileSelected={handleFileSelected} />
      <div style={{ flex: 1 }}>
        <Sender
          onSubmit={handleSubmit}
          placeholder={disabled ? "AI 正在思考中..." : "输入消息..."}
          value={message}
          onChange={setMessage}
          disabled={disabled}
        />
      </div>
    </div>
  );
};

export default AgentChatInput;
