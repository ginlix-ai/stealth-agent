import React, { useState } from 'react';
import './HtmlViewer.css';

export default function HtmlViewer({ content }) {
  const [mode, setMode] = useState('preview');

  return (
    <div className="html-viewer">
      <div className="html-viewer-toolbar">
        <button
          className={`html-viewer-tab ${mode === 'preview' ? 'active' : ''}`}
          onClick={() => setMode('preview')}
        >
          Preview
        </button>
        <button
          className={`html-viewer-tab ${mode === 'source' ? 'active' : ''}`}
          onClick={() => setMode('source')}
        >
          Source
        </button>
      </div>
      {mode === 'preview' ? (
        <iframe
          srcDoc={content}
          sandbox="allow-same-origin"
          className="html-viewer-frame"
          title="HTML Preview"
        />
      ) : (
        <pre className="html-viewer-source"><code>{content}</code></pre>
      )}
    </div>
  );
}
