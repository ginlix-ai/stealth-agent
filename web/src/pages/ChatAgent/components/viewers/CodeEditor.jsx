import Editor, { DiffEditor } from '@monaco-editor/react';

const EXT_TO_MONACO_LANG = {
  py: 'python', js: 'javascript', jsx: 'javascript', ts: 'typescript', tsx: 'typescript',
  json: 'json', md: 'markdown', yaml: 'yaml', yml: 'yaml', sql: 'sql',
  sh: 'shell', bash: 'shell', rs: 'rust', rb: 'ruby', go: 'go', java: 'java',
  xml: 'xml', css: 'css', html: 'html', htm: 'html', toml: 'ini', cfg: 'ini', ini: 'ini',
  txt: 'plaintext', csv: 'plaintext', env: 'shell', log: 'plaintext',
};

function getLanguageFromFileName(fileName) {
  const ext = (fileName || '').split('.').pop()?.toLowerCase() || '';
  return EXT_TO_MONACO_LANG[ext] || 'plaintext';
}

function getTheme() {
  if (typeof document !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'light') {
    return 'vs';
  }
  return 'vs-dark';
}

const EDITOR_OPTIONS = {
  minimap: { enabled: false },
  lineNumbers: 'on',
  wordWrap: 'on',
  scrollBeyondLastLine: false,
  fontSize: 12,
  automaticLayout: true,
  padding: { top: 8 },
};

export default function CodeEditor({ value, onChange, fileName, readOnly = false, height = '100%', diffMode = false, originalValue, editorRef, onUndoRedoChange }) {
  const language = getLanguageFromFileName(fileName);
  const theme = getTheme();
  const showDiff = diffMode && originalValue != null;

  return (
    <div style={{ position: 'relative', height, width: '100%' }}>
      {/* Always-mounted editor — preserves undo stack across diff toggles */}
      <div style={showDiff ? { position: 'absolute', inset: 0, visibility: 'hidden', pointerEvents: 'none' } : { height: '100%' }}>
        <Editor
          height="100%"
          language={language}
          theme={theme}
          value={value ?? ''}
          onMount={(editor) => {
            if (editorRef) editorRef.current = editor;
            let undoDepth = 0;
            let redoDepth = 0;
            onUndoRedoChange?.({ canUndo: false, canRedo: false });
            editor.onDidChangeModelContent((e) => {
              if (e.isUndoing) {
                undoDepth--;
                redoDepth++;
              } else if (e.isRedoing) {
                undoDepth++;
                redoDepth--;
              } else {
                undoDepth++;
                redoDepth = 0;
              }
              onUndoRedoChange?.({ canUndo: undoDepth > 0, canRedo: redoDepth > 0 });
              onChange?.(editor.getValue());
            });
          }}
          options={{ ...EDITOR_OPTIONS, readOnly }}
        />
      </div>
      {/* Diff overlay — edits here flow back to the normal editor via onChange → value prop */}
      {showDiff && (
        <div style={{ position: 'absolute', inset: 0 }}>
          <DiffEditor
            height="100%"
            language={language}
            theme={theme}
            original={originalValue}
            modified={value ?? ''}
            onMount={(diffEditor) => {
              const modifiedEditor = diffEditor.getModifiedEditor();
              modifiedEditor.onDidChangeModelContent(() => {
                onChange?.(modifiedEditor.getValue());
              });
            }}
            options={{ ...EDITOR_OPTIONS, readOnly, renderSideBySide: true }}
          />
        </div>
      )}
    </div>
  );
}
