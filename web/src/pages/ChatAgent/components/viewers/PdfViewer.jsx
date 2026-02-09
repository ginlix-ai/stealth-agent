import React, { useState, useCallback, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import './PdfViewer.css';

// Vite-native ?url import resolves correctly in both dev and build
import pdfjsWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
pdfjs.GlobalWorkerOptions.workerSrc = pdfjsWorkerUrl;

const ZOOM_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];
const DEFAULT_ZOOM_INDEX = 2; // 1.0

export default function PdfViewer({ data }) {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [zoomIndex, setZoomIndex] = useState(DEFAULT_ZOOM_INDEX);
  const [error, setError] = useState(null);

  const scale = ZOOM_STEPS[zoomIndex];

  const onDocumentLoadSuccess = useCallback(({ numPages: n }) => {
    setNumPages(n);
    setPageNumber(1);
  }, []);

  const goToPrev = () => setPageNumber((p) => Math.max(1, p - 1));
  const goToNext = () => setPageNumber((p) => Math.min(numPages || 1, p + 1));
  const zoomIn = () => setZoomIndex((i) => Math.min(ZOOM_STEPS.length - 1, i + 1));
  const zoomOut = () => setZoomIndex((i) => Math.max(0, i - 1));

  // Memoize once — pdf.js transfers the buffer to its web worker which detaches it,
  // so re-creating Uint8Array on subsequent renders would fail.
  const fileData = useMemo(() => {
    if (!data) return null;
    const bytes = data instanceof ArrayBuffer ? new Uint8Array(data) : data;
    return { data: bytes };
  }, [data]);

  // Bubble errors to the error boundary via render-phase throw
  if (error) throw error;

  return (
    <div className="pdf-viewer">
      {/* Controls */}
      <div className="pdf-controls">
        <div className="pdf-nav">
          <button onClick={goToPrev} disabled={pageNumber <= 1} className="pdf-btn">
            Prev
          </button>
          <span className="pdf-page-info">
            {pageNumber} / {numPages ?? '...'}
          </span>
          <button onClick={goToNext} disabled={pageNumber >= (numPages || 1)} className="pdf-btn">
            Next
          </button>
        </div>
        <div className="pdf-zoom">
          <button onClick={zoomOut} disabled={zoomIndex <= 0} className="pdf-btn">
            −
          </button>
          <span className="pdf-zoom-info">{Math.round(scale * 100)}%</span>
          <button onClick={zoomIn} disabled={zoomIndex >= ZOOM_STEPS.length - 1} className="pdf-btn">
            +
          </button>
        </div>
      </div>

      {/* Document */}
      <div className="pdf-document-wrapper">
        <Document
          file={fileData}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={(err) => setError(err)}
          loading={
            <div className="pdf-loading">Loading PDF...</div>
          }
        >
          <Page
            pageNumber={pageNumber}
            scale={scale}
            loading={<div className="pdf-loading">Rendering page...</div>}
          />
        </Document>
      </div>
    </div>
  );
}
