import React, { useState, useEffect, useMemo } from 'react';
import ExcelJS from 'exceljs';
import './ExcelViewer.css';

const MAX_PREVIEW_ROWS = 500;

// Default Office theme colors for when theme index is used without resolved ARGB
const DEFAULT_THEME_COLORS = [
  'FFFFFF', '000000', 'E7E6E6', '44546A',
  '4472C4', 'ED7D31', 'A5A5A5', 'FFC000', '5B9BD5', '70AD47',
];

function applyTint(hex, tint) {
  if (!tint) return hex;
  let r = parseInt(hex.slice(0, 2), 16);
  let g = parseInt(hex.slice(2, 4), 16);
  let b = parseInt(hex.slice(4, 6), 16);
  if (tint > 0) {
    r = Math.round(r + (255 - r) * tint);
    g = Math.round(g + (255 - g) * tint);
    b = Math.round(b + (255 - b) * tint);
  } else {
    r = Math.round(r * (1 + tint));
    g = Math.round(g * (1 + tint));
    b = Math.round(b * (1 + tint));
  }
  const clamp = (v) => Math.max(0, Math.min(255, v));
  r = clamp(r); g = clamp(g); b = clamp(b);
  return r.toString(16).padStart(2, '0') + g.toString(16).padStart(2, '0') + b.toString(16).padStart(2, '0');
}

function resolveColor(color) {
  if (!color) return null;
  if (color.argb) {
    const argb = color.argb;
    // ARGB format: skip alpha channel
    return '#' + (argb.length === 8 ? argb.slice(2) : argb);
  }
  if (color.theme != null) {
    const base = DEFAULT_THEME_COLORS[color.theme] || '000000';
    return '#' + (color.tint ? applyTint(base, color.tint) : base);
  }
  return null;
}

function getCellStyle(cell) {
  const style = {};
  if (!cell) return style;

  // Background fill
  const fill = cell.fill;
  if (fill?.type === 'pattern' && fill.pattern !== 'none' && fill.fgColor) {
    const bg = resolveColor(fill.fgColor);
    if (bg) style.backgroundColor = bg;
  }

  // Font
  const font = cell.font;
  if (font) {
    if (font.bold) style.fontWeight = 'bold';
    if (font.italic) style.fontStyle = 'italic';
    const decorations = [];
    if (font.underline) decorations.push('underline');
    if (font.strike) decorations.push('line-through');
    if (decorations.length) style.textDecoration = decorations.join(' ');
    const fontColor = resolveColor(font.color);
    if (fontColor) style.color = fontColor;
    if (font.size) style.fontSize = `${font.size}pt`;
  }

  // Alignment
  const align = cell.alignment;
  if (align) {
    if (align.horizontal) style.textAlign = align.horizontal;
    if (align.vertical === 'middle') style.verticalAlign = 'middle';
    else if (align.vertical === 'top') style.verticalAlign = 'top';
    if (align.wrapText) style.whiteSpace = 'pre-wrap';
  }

  return style;
}

function getCellDisplayValue(cell) {
  if (!cell || cell.value == null) return '';
  const v = cell.value;
  if (typeof v === 'object') {
    if (v.richText) return v.richText.map((r) => r.text).join('');
    if (v.result != null) return String(v.result);
    if (v instanceof Date) return v.toLocaleDateString();
    if (v.hyperlink) return v.text || v.hyperlink;
    if (v.error) return v.error;
  }
  return String(v);
}

/** Parse workbook into plain data (runs async in effect) */
async function parseWorkbook(buffer) {
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.load(buffer);

  return wb.worksheets.map((ws) => {
    const colCount = ws.columnCount;
    const rowCount = ws.rowCount;
    const previewCount = Math.min(rowCount, MAX_PREVIEW_ROWS);
    const rows = [];

    for (let r = 1; r <= previewCount; r++) {
      const row = ws.getRow(r);
      const cells = [];
      for (let c = 1; c <= colCount; c++) {
        const cell = row.getCell(c);
        cells.push({
          value: getCellDisplayValue(cell),
          style: getCellStyle(cell),
        });
      }
      rows.push(cells);
    }

    return { name: ws.name, rows, totalRows: rowCount };
  });
}

export default function ExcelViewer({ data }) {
  const [sheets, setSheets] = useState(null);
  const [activeSheet, setActiveSheet] = useState(0);
  const [parseError, setParseError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    parseWorkbook(data)
      .then((result) => { if (!cancelled) setSheets(result); })
      .catch((err) => {
        console.error('[ExcelViewer] Failed to parse workbook:', err);
        if (!cancelled) setParseError(err);
      });
    return () => { cancelled = true; };
  }, [data]);

  // Bubble to error boundary
  if (parseError) throw parseError;

  if (!sheets) {
    return <div className="excel-viewer-empty">Parsing spreadsheet...</div>;
  }
  if (sheets.length === 0) {
    throw new Error('No sheets found in workbook');
  }

  const sheet = sheets[activeSheet] || sheets[0];
  const { rows, totalRows } = sheet;

  if (rows.length === 0) {
    return <div className="excel-viewer-empty">This sheet is empty</div>;
  }

  const headerRow = rows[0];
  const dataRows = rows.slice(1);
  const truncated = totalRows > MAX_PREVIEW_ROWS;

  return (
    <div className="excel-viewer">
      {/* Sheet tabs */}
      {sheets.length > 1 && (
        <div className="excel-sheet-tabs">
          {sheets.map((s, idx) => (
            <button
              key={s.name}
              className={`excel-sheet-tab ${idx === activeSheet ? 'active' : ''}`}
              onClick={() => setActiveSheet(idx)}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}

      {/* Table */}
      <div className="excel-table-wrapper">
        <table className="excel-table">
          <thead>
            <tr>
              <th className="excel-row-num">#</th>
              {headerRow.map((cell, ci) => (
                <th key={ci} style={cell.style}>{cell.value}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataRows.map((row, ri) => (
              <tr key={ri}>
                <td className="excel-row-num">{ri + 1}</td>
                {row.map((cell, ci) => (
                  <td key={ci} style={cell.style}>{cell.value}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {truncated && (
        <div className="excel-truncated">
          Showing first {MAX_PREVIEW_ROWS} of {totalRows} rows
        </div>
      )}
    </div>
  );
}
