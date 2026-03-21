import { useRef, useState, type KeyboardEvent } from 'react';
import { Button, Upload, Space, Tooltip } from 'antd';
import { SendOutlined, PictureOutlined, DeleteOutlined } from '@ant-design/icons';
import { useAgentStore } from '../../stores/agent';

export default function ChatInput() {
  const [text, setText] = useState('');
  const [images, setImages] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useAgentStore((s) => s.sendMessage);
  const isStreaming = useAgentStore((s) => s.isStreaming);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed && images.length === 0) return;
    sendMessage(trimmed, images.length > 0 ? images : undefined);
    setText('');
    setImages([]);
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleImageUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = (reader.result as string).split(',')[1];
      setImages((prev) => [...prev, base64]);
    };
    reader.readAsDataURL(file);
    return false; // prevent default upload
  };

  return (
    <div style={{ borderTop: '1px solid #1e2126', padding: '12px 16px', background: '#0f1114' }}>
      {/* Image previews */}
      {images.length > 0 && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
          {images.map((img, i) => (
            <div
              key={i}
              style={{
                position: 'relative',
                width: 64,
                height: 64,
                borderRadius: 6,
                overflow: 'hidden',
                border: '1px solid #2b2f36',
              }}
            >
              <img
                src={`data:image/png;base64,${img}`}
                alt=""
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
              <Button
                size="small"
                type="text"
                icon={<DeleteOutlined />}
                onClick={() => setImages((prev) => prev.filter((_, idx) => idx !== i))}
                style={{
                  position: 'absolute',
                  top: 0,
                  right: 0,
                  color: '#f6465d',
                  background: 'rgba(0,0,0,0.6)',
                  border: 'none',
                  padding: 0,
                  width: 20,
                  height: 20,
                  minWidth: 20,
                }}
              />
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <Upload
          accept="image/*"
          showUploadList={false}
          beforeUpload={handleImageUpload}
          multiple
        >
          <Tooltip title="上传图片">
            <Button
              icon={<PictureOutlined />}
              size="small"
              style={{
                background: '#1a1d21',
                borderColor: '#2b2f36',
                color: '#848e9c',
                height: 36,
                width: 36,
              }}
            />
          </Tooltip>
        </Upload>

        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            background: '#1a1d21',
            border: '1px solid #2b2f36',
            borderRadius: 8,
            padding: '8px 12px',
            color: '#eaecef',
            fontSize: 13,
            fontFamily: 'inherit',
            outline: 'none',
            minHeight: 36,
            maxHeight: 120,
            lineHeight: '20px',
          }}
        />

        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={isStreaming}
          disabled={isStreaming || (!text.trim() && images.length === 0)}
          style={{ height: 36, width: 36, padding: 0 }}
        />
      </div>
    </div>
  );
}
