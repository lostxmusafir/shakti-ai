import { useState } from 'react';
import type { Result } from './types';
import { Icon } from './Icons';
import MarkdownView from './MarkdownView';

export default function ResultCard({ result, onRetry }: { result: Result; onRetry?: () => void }) {
  const [copied, setCopied] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);

  function copyAnswer() {
    const text = result.answer;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {});
  }

  return (
    <div className="claude-response-turn">
      {/* Claude Message Header */}
      <div className="claude-response-header">
        <span className="claude-spark-icon" aria-hidden="true">✳</span>
        <span className="claude-author-name">Claude</span>
      </div>

      {/* Formatted Markdown Content */}
      <div className="claude-response-body">
        <MarkdownView content={result.answer} />

        {/* Supplementary Table if data rows returned */}
        {result.rows && result.rows.length > 0 && result.columns && result.columns.length > 0 && (
          <div className="claude-table-wrap">
            <table className="claude-table">
              <thead>
                <tr>
                  {result.columns.map((c, i) => (
                    <th key={`${c}-${i}`}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.slice(0, 20).map((r, i) => (
                  <tr key={i}>
                    {r.map((c, j) => (
                      <td key={j}>{c === null ? '—' : String(c)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {result.rows.length > 20 && (
              <p className="claude-table-caption">
                Showing 20 of {result.rows.length} records.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Claude Action Toolbar */}
      <div className="claude-action-bar">
        <button
          className="claude-ghost-btn"
          onClick={copyAnswer}
          title="Copy response"
          aria-label="Copy response"
        >
          <Icon name={copied ? 'check' : 'file'} size={14} />
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>

        {onRetry && (
          <button
            className="claude-ghost-btn"
            onClick={onRetry}
            title="Retry"
            aria-label="Retry"
          >
            <Icon name="refresh" size={14} />
          </button>
        )}

        <button
          className={`claude-ghost-btn icon-only ${feedback === 'up' ? 'active' : ''}`}
          onClick={() => setFeedback(feedback === 'up' ? null : 'up')}
          title="Good response"
          aria-label="Thumbs up"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
          </svg>
        </button>

        <button
          className={`claude-ghost-btn icon-only ${feedback === 'down' ? 'active' : ''}`}
          onClick={() => setFeedback(feedback === 'down' ? null : 'down')}
          title="Bad response"
          aria-label="Thumbs down"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"/>
          </svg>
        </button>

        {/* Subtle Analysis Evidence Disclosure */}
        <button
          className="claude-evidence-toggle"
          onClick={() => setShowEvidence(!showEvidence)}
          title="View verified dataset details"
        >
          <span>{result.row_count ? `${result.row_count.toLocaleString()} rows verified` : 'Evidence details'}</span>
          <Icon name="chevron" size={11} className={showEvidence ? 'rotate-180' : ''} />
        </button>
      </div>

      {/* Subtle Evidence Drawer */}
      {showEvidence && (
        <div className="claude-evidence-drawer">
          <div className="claude-evidence-grid">
            <div>
              <span className="evidence-label">Method</span>
              <span className="evidence-val">{result.method}</span>
            </div>
            <div>
              <span className="evidence-label">Table</span>
              <span className="evidence-val">{result.table_name || 'Active sheet'}</span>
            </div>
            {result.excluded_rows !== undefined && result.excluded_rows > 0 && (
              <div>
                <span className="evidence-label">Excluded rows</span>
                <span className="evidence-val">{result.excluded_rows}</span>
              </div>
            )}
            {result.filters && result.filters.length > 0 && (
              <div>
                <span className="evidence-label">Filters</span>
                <span className="evidence-val">
                  {result.filters.map(f => `${f.column} ${f.op} ${Array.isArray(f.value) ? f.value.join(', ') : f.value}`).join('; ')}
                </span>
              </div>
            )}
          </div>
          {result.warnings && result.warnings.length > 0 && (
            <div className="claude-evidence-notes">
              <strong>Notes:</strong>
              <ul>
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
