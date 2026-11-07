import { useState } from 'react';
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
}

export default function CloneHome({
  username,
  onUpload,
  onSample,
  busy,
  draft,
  setDraft,
  onSubmitDraft,
  hasDatasets
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
        <span>Zydrakon AI · SQLite + Cloud AI · English & Hinglish</span>
      </div>

      <div className="clone-greeting-block">
        <span className="clone-spark" aria-hidden="true">✳</span>
        <h1>{greeting}, {username}</h1>
      </div>

      <div className="clone-composer">
        <textarea
          aria-label="Ask a question about your data in English or Hinglish"
          placeholder="Ask in English or Hinglish (e.g. Sabse zyada incidents kis port par hain?)"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          maxLength={2000}
          rows={3}
        />
        <div className="clone-composer-bar">
          <span className="model-tag">
            <Icon name="cloud" size={13} />
            <span>OpenAI Responses · Cloud AI</span>
          </span>
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
            disabled={busy}
            title={draft.trim() ? (hasDatasets ? "Submit question" : "Upload data to answer this question") : "Upload data to begin"}
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
