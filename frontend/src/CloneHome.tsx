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
  // Time-aware greeting
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  const suggestions = [
    'What are the key trends and patterns in this sheet?',
    'Show top 5 records by highest numbers',
    'Sabse zyada incidents kis port par hain?',
    'Identify duplicates, anomalies or blank entries'
  ];

  return (
    <section className="claude-home-container">
      {/* Centered Claude Greeting */}
      <div className="claude-home-hero">
        <span className="claude-hero-spark" aria-hidden="true">✳</span>
        <h1 className="claude-hero-title">{greeting}, {username}</h1>
      </div>

      {/* Claude Central Composer */}
      <div className="claude-composer-box">
        {selectedDataset && (
          <div className="claude-attached-chip">
            <span className="chip-icon"><Icon name="file" size={13} /></span>
            <span className="chip-name">{selectedDataset.name}</span>
            {totalRows !== undefined && <span className="chip-rows">· {totalRows.toLocaleString()} rows</span>}
            {onDetach && (
              <button
                type="button"
                className="chip-remove"
                onClick={onDetach}
                title="Detach spreadsheet"
                aria-label="Detach spreadsheet"
              >
                ×
              </button>
            )}
          </div>
        )}

        <textarea
          className="claude-textarea"
          aria-label="Ask Claude about your spreadsheet"
          placeholder={selectedDataset ? `Ask Claude anything about ${selectedDataset.name}...` : 'How can Claude help you with your spreadsheets today?'}
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

        <div className="claude-composer-controls">
          <div className="composer-controls-left">
            <button
              type="button"
              className="claude-attach-pill"
              onClick={onUpload}
              title="Attach CSV or Excel spreadsheet"
              disabled={busy}
            >
              <Icon name="upload" size={13} />
              <span>Attach sheet</span>
            </button>
            <div className="claude-model-badge">
              <span className="claude-spark-icon">✳</span>
              <span>Claude 3.5 Sonnet</span>
            </div>
          </div>

          <button
            type="button"
            aria-label="Send to Claude"
            className={`claude-send-circle ${draft.trim() ? 'active' : ''}`}
            onClick={() => {
              if (onSubmitDraft && draft.trim()) {
                onSubmitDraft();
              } else {
                onUpload();
              }
            }}
            disabled={busy || !draft.trim()}
            title={draft.trim() ? 'Send to Claude' : 'Type a question'}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="19" x2="12" y2="5" />
              <polyline points="5 12 12 5 19 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Suggestion Cards */}
      <div className="claude-suggestions-grid">
        {suggestions.map(label => (
          <button
            key={label}
            type="button"
            className="claude-suggestion-card"
            onClick={() => {
              setDraft(label);
              if (!hasDatasets) {
                onUpload();
              }
            }}
          >
            <span className="suggestion-spark">✳</span>
            <span className="suggestion-text">{label}</span>
          </button>
        ))}
      </div>

      {/* Clean Call To Action if no spreadsheet uploaded yet */}
      {!hasDatasets && (
        <div className="claude-cta-group">
          <button type="button" className="claude-pill-cta primary" onClick={onUpload} disabled={busy}>
            <Icon name="upload" size={15} />
            <span>Upload CSV or Excel sheet</span>
          </button>
          <button type="button" className="claude-pill-cta secondary" onClick={onSample} disabled={busy}>
            <Icon name="grid" size={15} />
            <span>Load demo firewall dataset</span>
          </button>
        </div>
      )}
    </section>
  );
}
