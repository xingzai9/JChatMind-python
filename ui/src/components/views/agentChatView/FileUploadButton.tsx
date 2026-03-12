import React, { useState, useRef } from "react";
import { Button, message, Space, Tag } from "antd";
import { PaperClipOutlined, CloseOutlined } from "@ant-design/icons";

interface FileUploadButtonProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

const FileUploadButton: React.FC<FileUploadButtonProps> = ({
  onFileSelected,
  disabled = false,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const SUPPORTED_TYPES = ["pdf", "docx", "xlsx", "pptx"];
  const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 验证文件类型
    const fileExtension = file.name.split(".").pop()?.toLowerCase();
    if (!fileExtension || !SUPPORTED_TYPES.includes(fileExtension)) {
      message.error(
        `不支持的文件类型。仅支持: ${SUPPORTED_TYPES.join(", ")}`,
      );
      return;
    }

    // 验证文件大小
    if (file.size > MAX_FILE_SIZE) {
      message.error("文件大小超过限制（最大 100MB）");
      return;
    }

    setSelectedFile(file);
    onFileSelected(file);
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.xlsx,.pptx"
        style={{ display: "none" }}
        onChange={handleFileChange}
        disabled={disabled}
      />

      {!selectedFile ? (
        <Button
          icon={<PaperClipOutlined />}
          onClick={handleButtonClick}
          disabled={disabled}
          type="text"
        />
      ) : (
        <Space
          style={{
            padding: "8px 12px",
            background: "#f0f0f0",
            borderRadius: 4,
            marginBottom: 8,
          }}
        >
          <PaperClipOutlined />
          <span style={{ fontSize: 14 }}>{selectedFile.name}</span>
          <Tag color="blue">{formatFileSize(selectedFile.size)}</Tag>
          <CloseOutlined
            style={{ cursor: "pointer", color: "#999" }}
            onClick={handleRemoveFile}
          />
        </Space>
      )}
    </div>
  );
};

export default FileUploadButton;


