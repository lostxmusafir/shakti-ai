import { useState } from 'react';
import type { Dataset } from './types';
import { Icon } from './Icons';

interface CloneHomeProps {
  username: string;
  onUpload: () => void;
  onSample: () => void;
  busy: boolean;
  draft: string;
  setDraft: (value: string) => void;
  onSubmitDraft?: () => void;
  hasDatasets?: boolean;
  selectedDataset?: Dataset | null;
  totalRows?: number;
  onDetach?: () => void;
}

export default function CloneHome({
  username,
  onUpload,
  onSample,
  busy,
  draft,
  setDraft,
  onSubmitDraft,
  hasDatasets,
  selectedDataset,
  totalRows,
  onDetach
}: CloneHomeProps) {
  const [showSuggestions, setShowSuggestions] = useState(true);

  // Time-aware greeting
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  const suggestions = [
    'Explore a company spreadsheet',
    'Compare department totals',
    'Find top 5 expenses by amount',
    'Sabse zyada incidents kis port par hain?',
    'Identify duplicate records and blanks'
  ];

  return (
    <section className="clone-welcome">
      <div className="clone-status-pill">
        <span>Claude 3.5 Sonnet · Spreadsheet Assistant</span>
      </div>

      <div className="clone-greeting-block">
        <span className="clone-spark" aria-hidden="true">✳</span>
        <h1>{greeting}, {username}</h1>
      </div>

      <div className="clone-composer">
        {selectedDataset && (
          <div className="clone-attached-pill">
            <span className="attached-icon"><Icon name="file" size={14} /></span>
            <strong>{selectedDataset.name}</strong>
            {totalRows !== undefined && <span className="attached-rows">({totalRows.toLocaleString()} rows)</span>}
            {onDetach && (
              <button className="pill-remove" onClick={onDetach} title="Detach spreadsheet" aria-label="Detach">
                ×
              </button>
            )}
          </div>
        )}
        <textarea
          aria-label="Ask Claude about your spreadsheet"
          placeholder={selectedDataset ? `Ask Claude anything about ${selectedDataset.name} in English or Hinglish...` : "How can Claude help you with your spreadsheets today?"}
          value={draft}
          onChange={e => setDraft(e.target.value)}
          maxLength={2000}
          rows={3}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              if (onSubmitDraft && draft.trim()) {
                onSubmitDraft();
              }
            }
          }}
        />
        <div className="clone-composer-bar">
          <div className="composer-bar-left">
            <button className="attach-button" onClick={onUpload} title="Attach CSV or Excel spreadsheet" disabled={busy}>
              <Icon name="upload" size={14} />
              <span>Attach sheet</span>
            </button>
            <span className="model-tag">
              <span className="clone-spark-icon" style={{ color: '#b6613c', fontSize: '13px' }}>✳</span>
              <span>Claude 3.5 Sonnet</span>
            </span>
          </div>
          <button
            aria-label="Start analysis"
            className={`send-circle ${draft.trim() ? 'active' : ''}`}
            onClick={() => {
              if (onSubmitDraft && draft.trim()) {
                onSubmitDraft();
              } else {
                onUpload();
              }
            }}
            disabled={busy || !draft.trim()}
            title={draft.trim() ? "Send to Claude" : "Type a question"}
          >
            <Icon name="arrow" size={18} />
          </button>
        </div>
      </div>

      <div className="clone-home-tools">
        <button
          className="tool-toggle"
          onClick={() => setShowSuggestions(!showSuggestions)}
        >
          {showSuggestions ? 'Hide suggestions' : 'Get started with an example'}
        </button>
        <div className="tool-actions">
          <button
            className="tool-btn"
            onClick={onUpload}
            disabled={busy}
            title="Upload CSV, XLSX or clear table images"
          >
            <Icon name="upload" size={14} />
            <span>Add content</span>
          </button>
        </div>
      </div>

      {showSuggestions && (
        <div className="clone-suggestions">
          {suggestions.map(label => (
            <button
              key={label}
              onClick={() => {
                setDraft(label);
                if (!hasDatasets) {
                  onUpload();
                }
              }}
            >
              <span className="suggestion-spark">✳</span>
              <span>{label}</span>
            </button>
          ))}
        </div>
      )}

      <div className="clone-help-card">
        <div className="help-icon"><Icon name="shield" size={18} /></div>
        <div className="help-text">
          <strong>No dummy data — Real company datasets</strong>
          <p>Upload your real CSV, Excel (.xlsx), or clear table images. Files are stored locally in SQLite and calculations run on the full table with verifiable source evidence.</p>
        </div>
      </div>

      {!hasDatasets && (
        <div className="clone-cta-row">
          <button className="button primary" onClick={onUpload} disabled={busy}>
            <Icon name="upload" size={16} />
            <span>Upload your first spreadsheet</span>
          </button>
          <button className="button secondary" onClick={onSample} disabled={busy}>
            <Icon name="grid" size={16} />
            <span>Or load synthetic sample</span>
          </button>
        </div>
      )}
    </section>
  );
}
