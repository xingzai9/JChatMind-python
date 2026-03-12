import React from "react";
import { Card, Button, Typography, Space, Tag } from "antd";
import { DownloadOutlined, FileExcelOutlined, FilePdfOutlined, FileWordOutlined, FilePptOutlined, FileOutlined } from "@ant-design/icons";
import type { FileAttachment } from "../../../types";
import { getFileDownloadUrl } from "../../../api/api";

const { Text } = Typography;

interface FileCardProps {
  file: FileAttachment;
  showDownload?: boolean;
}

const FileCard: React.FC<FileCardProps> = ({ file, showDownload = true }) => {
  const getFileIcon = (fileType: string) => {
    switch (fileType.toLowerCase()) {
      case "xlsx":
        return <FileExcelOutlined style={{ fontSize: 24, color: "#1D6F42" }} />;
      case "pdf":
        return <FilePdfOutlined style={{ fontSize: 24, color: "#D32F2F" }} />;
      case "docx":
        return <FileWordOutlined style={{ fontSize: 24, color: "#2B579A" }} />;
      case "pptx":
        return <FilePptOutlined style={{ fontSize: 24, color: "#D24726" }} />;
      default:
        return <FileOutlined style={{ fontSize: 24, color: "#666" }} />;
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) {
      return `${bytes} B`;
    } else if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(2)} KB`;
    } else {
      return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    }
  };

  const handleDownload = () => {
    const url = getFileDownloadUrl(file.fileId);
    window.open(url, "_blank");
  };

  return (
    <Card
      size="small"
      style={{
        maxWidth: 400,
        borderRadius: 8,
        boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
      }}
    >
      <Space direction="vertical" style={{ width: "100%" }} size="small">
        <Space>
          {getFileIcon(file.fileType)}
          <div style={{ flex: 1 }}>
            <Text strong style={{ fontSize: 14 }}>
              {file.fileName}
            </Text>
            <br />
            <Space size="small">
              <Tag color="blue">{file.fileType.toUpperCase()}</Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {formatFileSize(file.fileSize)}
              </Text>
            </Space>
          </div>
        </Space>

        {file.summary && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {file.summary}
          </Text>
        )}

        {showDownload && (
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            size="small"
            onClick={handleDownload}
            block
          >
            下载文件
          </Button>
        )}
      </Space>
    </Card>
  );
};

export default FileCard;


