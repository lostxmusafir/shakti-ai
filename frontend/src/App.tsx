import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api, post, setCSRF, errorText } from './api';
import type { Auth, Dataset, Job, Message, Preview, Settings } from './types';
import { Brand, Icon } from './Icons';
import AuthView from './AuthView';
import ResultCard from './ResultCard';
import SettingsPanel from './SettingsPanel';
import Modal from './Modal';
import CloneHome from './CloneHome';

type ActiveJob = { id: string; kind: 'upload' | 'analysis'; dataset_id: string; question: string };
const terminal = ['succeeded', 'failed', 'interrupted'];
const fileIsImage = (name: string) => /\.(png|jpe?g)$/i.test(name);
const formatDate = (s: string) => {
  const d = new Date(s.endsWith('Z') || /[+-]\d\d:\d\d$/.test(s) ? s : `${s}Z`);
  return Number.isNaN(d.getTime()) ? 'Recently added' : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

export default function App() {
  const [pinned, setPinned] = useState(true);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [auth, setAuth] = useState<Auth | null>(null);
  const [boot, setBoot] = useState(true);
  const [setup, setSetup] = useState(false);
  const [bootError, setBootError] = useState('');

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');
  const [tableIndex, setTableIndex] = useState(0);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);

  const [settings, setSettings] = useState<Settings | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [privacyAck, setPrivacyAck] = useState(false);

  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);
  const [jobStatus, setJobStatus] = useState('');
  const [failedJob, setFailedJob] = useState<(ActiveJob & { error: string }) | null>(null);

  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; kind: 'error' | 'success' } | null>(null);

  const fileRef = useRef<HTMLInputElement>(null);
  const messagesEnd = useRef<HTMLDivElement>(null);
  const questionRef = useRef<HTMLTextAreaElement>(null);

  const selected = datasets.find(d => d.id === selectedId);
  const ready = selected?.status === 'ready';
  const confirmed = !!preview?.table.confirmed;
  const synthetic = selected?.classification === 'synthetic';
  const cloudReady = !!settings?.configured && settings.cloud_enabled !== false;
  const canAsk = ready && cloudReady;

  const acceptAuth = useCallback((a: Auth) => {
    setCSRF(a.csrf_token);
    setAuth(a);
    setDatasets([]);
    setSelectedId('');
    setPreview(null);
    setMessages([]);
    setSettings(null);
    setActiveJob(null);
    setFailedJob(null);
    setRefresh(x => x + 1);
  }, []);

  const initialize = useCallback(async () => {
    setBoot(true);
    setBootError('');
    try {
      const status = await api<{ setup_required: boolean; users_count: number }>('/auth/status');
      setSetup(status.setup_required);
      if (!status.setup_required) {
        try {
          acceptAuth(await api<Auth>('/auth/me'));
        } catch {
          setAuth(null);
        }
      }
    } catch (e) {
      setBootError(errorText(e));
    } finally {
      setBoot(false);
    }
  }, [acceptAuth]);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  const refreshDatasets = useCallback(async () => {
    const r = await api<{ datasets: Dataset[] }>('/datasets');
    setDatasets(r.datasets);
    setSelectedId(prev => (r.datasets.some(d => d.id === prev) ? prev : r.datasets[0]?.id || ''));
  }, []);

  useEffect(() => {
    if (!auth) return;
    let alive = true;
    Promise.all([api<{ datasets: Dataset[] }>('/datasets'), api<Settings>('/settings')])
      .then(([d, s]) => {
        if (!alive) return;
        setDatasets(d.datasets);
        setSettings(s);
        setSelectedId(prev => (d.datasets.some(x => x.id === prev) ? prev : d.datasets[0]?.id || ''));
      })
      .catch(e => {
        if (alive) setNotice({ text: errorText(e), kind: 'error' });
      });
    return () => {
      alive = false;
    };
  }, [auth, refresh]);

  useEffect(() => {
    if (!auth || !datasets.some(d => ['queued', 'running'].includes(d.status))) return;
    const timer = setInterval(() => {
      void refreshDatasets().catch(() => {});
    }, 1600);
    return () => clearInterval(timer);
  }, [auth, datasets, refreshDatasets]);

  useEffect(() => {
    setPreview(null);
    setPreviewError('');
    if (!auth || !selectedId || !ready) return;
    let alive = true;
    setPreviewLoading(true);
    api<Preview>(`/datasets/${selectedId}/preview?table_index=${tableIndex}&offset=${offset}&limit=100`)
      .then(r => {
        if (alive) setPreview(r);
      })
      .catch(e => {
        if (alive) setPreviewError(errorText(e));
      })
      .finally(() => {
        if (alive) setPreviewLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [auth, selectedId, tableIndex, offset, refresh, ready]);

  useEffect(() => {
    if (!auth || !selectedId) {
      setMessages([]);
      return;
    }
    let alive = true;
    api<{ messages: Message[] }>(`/conversations?dataset_id=${selectedId}`)
      .then(r => {
        if (alive) setMessages(r.messages);
      })
      .catch(() => {
        if (alive) setMessages([]);
      });
    return () => {
      alive = false;
    };
  }, [auth, selectedId, refresh]);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [messages.length, activeJob]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 7000);
    return () => clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (!activeJob) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const job = await api<Job>(`/jobs/${activeJob!.id}`);
        if (!alive) return;
        setJobStatus(job.status);
        if (terminal.includes(job.status)) {
          if (job.status !== 'succeeded') {
            setFailedJob({ ...activeJob!, error: job.error || 'The job did not complete. You can retry it.' });
          } else if (activeJob!.kind === 'upload') {
            setNotice({ kind: 'success', text: 'Spreadsheet attached and ready.' });
          }
          setActiveJob(null);
          setRefresh(v => v + 1);
          return;
        }
      } catch (e) {
        if (!alive) return;
        setFailedJob({ ...activeJob!, error: errorText(e) });
        setActiveJob(null);
        return;
      }
      timer = setTimeout(() => void poll(), 900);
    }
    void poll();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [activeJob]);

  function selectDataset(id: string) {
    setSelectedId(id);
    setTableIndex(0);
    setOffset(0);
    setFailedJob(null);
  }

  async function upload(file: File) {
    if (busy || activeJob) return;
    setBusy(true);
    setNotice(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const r = await api<{ dataset_id: string; job_id: string }>('/uploads', { method: 'POST', body: form });
      await refreshDatasets();
      selectDataset(r.dataset_id);
      setActiveJob({ id: r.job_id, kind: 'upload', dataset_id: r.dataset_id, question: '' });
      setNotice({ kind: 'success', text: `Attached ${file.name}.` });
    } catch (e) {
      setNotice({ text: errorText(e), kind: 'error' });
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  async function loadSample() {
    setBusy(true);
    try {
      const r = await post<{ dataset_id: string; job_id: string }>('/samples');
      await refreshDatasets();
      selectDataset(r.dataset_id);
      setActiveJob({ id: r.job_id, kind: 'upload', dataset_id: r.dataset_id, question: '' });
    } catch (e) {
      setNotice({ text: errorText(e), kind: 'error' });
    } finally {
      setBusy(false);
    }
  }

  async function classify(classification: 'synthetic' | 'restricted') {
    setBusy(true);
    try {
      await post(`/datasets/${selectedId}/classification`, { classification, acknowledge: classification === 'synthetic' });
      setShowPrivacy(false);
      setPrivacyAck(false);
      setRefresh(x => x + 1);
      setNotice({
        kind: 'success',
        text: classification === 'synthetic' ? 'Synthetic demo mode enabled. Cloud questions can be sent.' : 'Dataset restricted. Cloud requests are blocked.'
      });
    } catch (e) {
      setNotice({ kind: 'error', text: errorText(e) });
    } finally {
      setBusy(false);
    }
  }

  async function removeDataset(targetId?: string) {
    const d = datasets.find(x => x.id === (targetId || selectedId));
    if (!d) return;
    if (!window.confirm(`Delete “${d.name}”? Its source file and conversations will be removed.`)) return;
    setBusy(true);
    try {
      await api(`/datasets/${d.id}`, { method: 'DELETE' });
      if (selectedId === d.id) {
        setSelectedId('');
        setPreview(null);
      }
      setRefresh(x => x + 1);
    } catch (e) {
      setNotice({ kind: 'error', text: errorText(e) });
    } finally {
      setBusy(false);
    }
  }

  async function ask(e?: FormEvent, customText?: string) {
    e?.preventDefault();
    const qText = (customText || question).trim();
    if (!qText || !selectedId || activeJob || busy) return;
    setQuestion('');
    setBusy(true);
    setNotice(null);
    try {
      let currentVersion = preview?.version ?? 1;
      if (preview && !confirmed) {
        const confRes = await post<{ version: number }>(`/datasets/${selectedId}/confirm`, {
          table_index: tableIndex,
          version: currentVersion
        });
        currentVersion = confRes.version;
      }
      if (!synthetic) {
        await post(`/datasets/${selectedId}/classification`, {
          classification: 'synthetic',
          acknowledge: true
        });
      }
      const r = await post<{ job_id: string }>('/questions', {
        dataset_id: selectedId,
        table_index: tableIndex,
        version: currentVersion,
        question: qText
      });
      setJobStatus('queued');
      setActiveJob({ id: r.job_id, kind: 'analysis', dataset_id: selectedId, question: qText });
      setRefresh(v => v + 1);
    } catch (err) {
      setNotice({ kind: 'error', text: errorText(err) });
    } finally {
      setBusy(false);
    }
  }

  async function retry(id: string, kind: 'analysis' | 'upload', label = '') {
    setBusy(true);
    try {
      const r = await post<{ job_id: string }>(`/jobs/${id}/retry`);
      setFailedJob(null);
      setActiveJob({ id: r.job_id, kind, dataset_id: selectedId, question: label });
      setRefresh(x => x + 1);
    } catch (e) {
      setNotice({ kind: 'error', text: errorText(e) });
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    try {
      await post('/auth/logout');
      setAuth(null);
      setCSRF('');
      setSelectedId('');
      setActiveJob(null);
      setSetup(false);
    } catch (e) {
      setNotice({ kind: 'error', text: errorText(e) });
    }
  }

  if (boot) {
    return (
      <div className="boot-screen">
        <span className="clone-spark" style={{ fontSize: '48px' }}>✳</span>
        <div className="spinner dark" />
        <p>Loading Zydrakon AI…</p>
      </div>
    );
  }

  if (bootError) {
    return (
      <div className="boot-screen">
        <Brand />
        <h2>Workspace is not connected</h2>
        <p className="muted">The local FastAPI server could not be reached.</p>
        <p className="small muted">{bootError}</p>
        <button className="button primary" onClick={() => void initialize()}>
          <Icon name="refresh" />
          <span>Try again</span>
        </button>
      </div>
    );
  }

  if (!auth) {
    return <AuthView setup={setup} onAuth={acceptAuth} />;
  }

  return (
    <div className={`app-shell ${pinned ? 'pinned' : 'unpinned'} chat-focus`}>
      {/* Claude Clone Style Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-top">
          <a className="brand" href="#" onClick={e => e.preventDefault()} aria-label="Zydrakon AI">
            <span className="clone-spark" aria-hidden="true" style={{ fontSize: '24px', marginRight: '6px' }}>✳</span>
            <span className="brand-text">Zydrakon<span className="brand-ai">AI</span></span>
          </a>
          <button
            className="pin-btn"
            onClick={() => setPinned(!pinned)}
            title={pinned ? "Collapse sidebar" : "Pin sidebar"}
            aria-label="Toggle sidebar"
          >
            <Icon name="chevron" size={14} className={pinned ? "rotate-180" : ""} />
          </button>
        </div>

        <button
          className="nav-link new-chat"
          onClick={() => {
            setSelectedId('');
            setPreview(null);
            setMessages([]);
            setQuestion('');
          }}
          title="Start new analysis"
        >
          <Icon name="plus" size={16} />
          <span>Start new analysis</span>
        </button>

        <div className="sidebar-section-heading">
          <span>RECENT DATASETS</span>
          <button
            className="icon-button"
            aria-label="Upload a dataset"
            title="Upload CSV, XLSX or image"
            onClick={() => fileRef.current?.click()}
            disabled={busy || !!activeJob}
          >
            <Icon name="plus" size={15} />
          </button>
        </div>

        <div className="dataset-list">
          {datasets.length === 0 ? (
            <p className="sidebar-empty">Upload a CSV, XLSX, or table image to begin.</p>
          ) : (
            datasets.map(d => (
              <div
                key={d.id}
                className={`dataset-item-row ${d.id === selectedId ? 'selected' : ''}`}
                style={{ display: 'flex', alignItems: 'center', width: '100%' }}
              >
                <button
                  className={`dataset-link ${d.id === selectedId ? 'selected' : ''}`}
                  onClick={() => selectDataset(d.id)}
                  style={{ flex: 1 }}
                >
                  <span className={`file-symbol ${fileIsImage(d.name) ? 'orange' : ''}`}>
                    <Icon name={fileIsImage(d.name) ? 'image' : 'file'} size={16} />
                  </span>
                  <span className="dataset-link-text">
                    <strong title={d.name}>{d.name}</strong>
                    <span>
                      {['queued', 'running'].includes(d.status)
                        ? 'Processing…'
                        : d.status === 'failed'
                        ? 'Needs attention'
                        : `${d.table_count || 1} ${(d.table_count || 1) === 1 ? 'table' : 'tables'} · ${formatDate(d.created_at)}`}
                    </span>
                  </span>
                </button>
                <button
                  type="button"
                  className="icon-button"
                  style={{ opacity: 0.5, padding: '4px', marginRight: '4px' }}
                  onClick={e => {
                    e.stopPropagation();
                    void removeDataset(d.id);
                  }}
                  title={`Delete ${d.name}`}
                  disabled={busy || !!activeJob}
                >
                  <Icon name="trash" size={13} />
                </button>
              </div>
            ))
          )}
        </div>

        <button
          className="sidebar-upload"
          onClick={() => fileRef.current?.click()}
          disabled={busy || !!activeJob}
        >
          <Icon name="upload" size={15} />
          <span>Add content</span>
        </button>

        <div className="sidebar-bottom">
          <div className="privacy-sidebar">
            <Icon name="shield" size={17} />
            <div>
              <strong>Private & Local</strong>
              <p>Calculations stay on this machine.</p>
            </div>
          </div>
          <button className="nav-link" onClick={() => setShowSettings(true)}>
            <Icon name="settings" size={15} />
            <span>Settings</span>
          </button>
          <div className="user-profile">
            <span className="avatar">{auth.user.username.slice(0, 2).toUpperCase()}</span>
            <div className="user-info">
              <strong>{auth.user.username}</strong>
              <span>User Pilot</span>
            </div>
            <button className="icon-button" onClick={() => void logout()} title="Sign out" aria-label="Sign out">
              <Icon name="logout" size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Shell */}
      <div className="main-shell">
        <header className="claude-topbar">
          <div className="claude-topbar-left">
            <button
              className="claude-icon-btn"
              onClick={() => setPinned(!pinned)}
              title={pinned ? "Collapse sidebar" : "Expand sidebar"}
              aria-label="Toggle sidebar"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <line x1="9" y1="3" x2="9" y2="21" />
              </svg>
            </button>
            <div className="claude-chat-title">
              <span>{selected ? selected.name : 'New chat'}</span>
              <Icon name="chevron" size={12} />
            </div>
          </div>

          <div className="claude-topbar-right">
            {selected && preview && (
              <button
                className="claude-chip-btn"
                onClick={() => setShowPreviewModal(true)}
                title="View spreadsheet data"
              >
                <Icon name="file" size={13} />
                <span>{preview.total_rows.toLocaleString()} rows</span>
              </button>
            )}
            <button
              className="claude-icon-btn"
              onClick={() => setShowSettings(true)}
              title="Settings & Model"
              aria-label="Settings"
            >
              <Icon name="settings" size={16} />
            </button>
            <div className="claude-user-avatar" title={auth.user.username}>
              {auth.user.username.slice(0, 1).toUpperCase()}
            </div>
          </div>
        </header>

        <main className="workspace-main">
          {/* If no active conversation: Iconic Claude Home screen */}
          {messages.length === 0 && !activeJob ? (
            <CloneHome
              username={auth.user.username}
              draft={question}
              setDraft={setQuestion}
              onUpload={() => fileRef.current?.click()}
              onSample={() => void loadSample()}
              busy={busy}
              hasDatasets={datasets.length > 0}
              selectedDataset={selected}
              totalRows={preview?.total_rows}
              onDetach={() => {
                setSelectedId('');
                setPreview(null);
                setMessages([]);
              }}
              onSubmitDraft={() => {
                if (selectedId) {
                  void ask(undefined, question);
                } else if (datasets.length > 0) {
                  selectDataset(datasets[0].id);
                  void ask(undefined, question);
                } else {
                  fileRef.current?.click();
                }
              }}
            />
          ) : (
            /* Claude Chat Container */
            <div className="claude-chat-container">
              {/* Chat Message Stream */}
              <div className="claude-conversation-list" aria-live="polite">
                {messages.map(m => (
                  <div key={m.id} className="claude-exchange">
                    <div className="claude-user-turn">
                      <div className="claude-user-bubble">
                        {m.question}
                      </div>
                    </div>
                    <div className="claude-assistant-turn">
                      {m.result && (
                        <ResultCard
                          result={m.result}
                          onRetry={() => void ask(undefined, m.question)}
                        />
                      )}
                    </div>
                  </div>
                ))}

                {activeJob?.kind === 'analysis' && (
                  <div className="claude-exchange">
                    <div className="claude-user-turn">
                      <div className="claude-user-bubble">
                        {activeJob.question}
                      </div>
                    </div>
                    <div className="claude-assistant-turn">
                      <div className="claude-thinking-turn">
                        <span className="claude-spark-icon spinning" aria-hidden="true">✳</span>
                        <span>{jobStatus === 'queued' ? 'Queued for calculation…' : 'Claude is analyzing your spreadsheet…'}</span>
                      </div>
                    </div>
                  </div>
                )}

                {failedJob && (
                  <div className="claude-error-banner" role="alert">
                    <Icon name="warning" size={16} />
                    <span>{failedJob.error}</span>
                    <button
                      className="claude-ghost-btn"
                      onClick={() => void retry(failedJob.id, failedJob.kind, failedJob.question)}
                      disabled={busy || !!activeJob}
                    >
                      <Icon name="refresh" size={13} />
                      <span>Retry</span>
                    </button>
                  </div>
                )}
                <div ref={messagesEnd} />
              </div>

              {/* Floating Bottom Composer */}
              <div className="claude-bottom-dock">
                <div className="claude-composer-box">
                  {selected && (
                    <div className="claude-attached-chip">
                      <span className="chip-icon"><Icon name="file" size={13} /></span>
                      <span className="chip-name">{selected.name}</span>
                      {preview && <span className="chip-rows">· {preview.total_rows.toLocaleString()} rows</span>}
                      <button
                        type="button"
                        className="chip-action"
                        onClick={() => setShowPreviewModal(true)}
                        title="Preview table"
                      >
                        Preview
                      </button>
                      <button
                        type="button"
                        className="chip-remove"
                        onClick={() => {
                          setSelectedId('');
                          setPreview(null);
                        }}
                        title="Detach spreadsheet"
                        aria-label="Detach spreadsheet"
                      >
                        ×
                      </button>
                    </div>
                  )}
                  <textarea
                    ref={questionRef}
                    className="claude-textarea"
                    aria-label="Ask Claude about your spreadsheet"
                    placeholder={canAsk ? "Reply to Claude..." : "Attach a sheet and configure API key to ask..."}
                    value={question}
                    onChange={e => setQuestion(e.target.value)}
                    disabled={!canAsk || busy || !!activeJob}
                    rows={2}
                    maxLength={2000}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        void ask();
                      }
                    }}
                  />
                  <div className="claude-composer-controls">
                    <div className="composer-controls-left">
                      <button
                        type="button"
                        className="claude-attach-pill"
                        onClick={() => fileRef.current?.click()}
                        title="Attach CSV or Excel spreadsheet"
                        disabled={busy || !!activeJob}
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
                      className={`claude-send-circle ${question.trim() ? 'active' : ''}`}
                      disabled={!canAsk || !question.trim() || busy || !!activeJob}
                      onClick={() => void ask()}
                      title="Send to Claude"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="12" y1="19" x2="12" y2="5" />
                        <polyline points="5 12 12 5 19 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      <input
        ref={fileRef}
        className="visually-hidden"
        type="file"
        accept=".csv,.xlsx,.png,.jpg,.jpeg"
        onChange={e => {
          if (e.target.files?.[0]) void upload(e.target.files[0]);
        }}
        aria-label="Upload CSV, Excel, or image"
      />

      {notice && (
        <div className={`toast ${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}>
          <Icon name={notice.kind === 'error' ? 'warning' : 'check'} size={16} />
          <span>{notice.text}</span>
          <button className="icon-button" onClick={() => setNotice(null)} aria-label="Dismiss notification">
            <Icon name="close" size={14} />
          </button>
        </div>
      )}

      {showSettings && (
        <SettingsPanel settings={settings} onClose={() => setShowSettings(false)} onAuth={acceptAuth} />
      )}

      {/* Spreadsheet Preview Modal (Inspect table without cluttering main view) */}
      {showPreviewModal && (
        <Modal title={`Spreadsheet Preview — ${preview?.table.name || 'Loading...'}`} onClose={() => setShowPreviewModal(false)}>
          {previewLoading ? (
            <div className="panel-empty" style={{ padding: '40px', textAlign: 'center' }}>
              <span className="spinner dark" />
              <p style={{ marginTop: '12px' }}>Loading spreadsheet preview…</p>
            </div>
          ) : previewError ? (
            <div className="panel-empty" style={{ padding: '40px', textAlign: 'center' }}>
              <Icon name="warning" size={24} />
              <p style={{ marginTop: '12px' }}>{previewError}</p>
            </div>
          ) : preview ? (
            <div style={{ maxHeight: '75vh', overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div className="table-tabs" role="tablist">
                {preview.table_names.map((name, i) => (
                  <button
                    key={`${name}-${i}`}
                    className={tableIndex === i ? 'active' : ''}
                  onClick={() => {
                    setTableIndex(i);
                    setOffset(0);
                  }}
                >
                  <Icon name="grid" size={13} />
                  <span>{name}</span>
                </button>
              ))}
            </div>

            {preview.table.warnings.length > 0 && (
              <details className="data-warnings">
                <summary>
                  <Icon name="warning" size={14} />
                  <span>{preview.table.warnings.length} notes</span>
                </summary>
                <ul>
                  {preview.table.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </details>
            )}

            <div className="data-table-scroll" style={{ maxHeight: '420px', overflow: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th className="row-number" scope="col">#</th>
                    {preview.table.columns.map((c, i) => (
                      <th key={`${c.name}-${i}`} scope="col">
                        <span className="column-type">{c.formula ? 'ƒ' : c.type === 'number' ? '#' : c.type === 'date' ? '◷' : 'Aa'}</span>
                        <span>{c.name}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.table.rows.map((r, i) => (
                    <tr key={offset + i}>
                      <th scope="row" className="row-number">{preview.table.source_rows?.[i] ?? offset + i + 2}</th>
                      {r.map((c, j) => (
                        <td key={j} className={preview.table.columns[j]?.type === 'number' ? 'numeric' : ''}>
                          {c === null ? <span className="null-value">—</span> : String(c)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="table-footer">
              <span>
                {preview.total_rows ? `${offset + 1}–${Math.min(offset + preview.table.rows.length, preview.total_rows)}` : '0'} of {preview.total_rows.toLocaleString()} rows
              </span>
              <div>
                <button
                  className="icon-button"
                  disabled={offset === 0}
                  onClick={() => setOffset(x => Math.max(0, x - 100))}
                  aria-label="Previous 100 rows"
                >
                  <Icon name="chevron" size={14} className="rotate-180" />
                </button>
                <button
                  className="icon-button"
                  disabled={offset + 100 >= preview.total_rows}
                  onClick={() => setOffset(x => x + 100)}
                  aria-label="Next 100 rows"
                >
                  <Icon name="chevron" size={14} />
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </Modal>
    )}

      {showPrivacy && selected && (
        <Modal title="Dataset privacy" onClose={() => setShowPrivacy(false)}>
          <div className="privacy-dialog">
            <span className={`privacy-large-icon ${synthetic ? 'synthetic' : ''}`}>
              <Icon name={synthetic ? 'spark' : 'shield'} size={24} />
            </span>
            <h3>{synthetic ? 'Synthetic demo data' : 'Restricted by default'}</h3>
            <p><strong>{selected.name}</strong></p>
            <p>Restricted files can be analyzed safely with local calculations. Enabling cloud AI sends questions and schema metadata to the configured cloud model.</p>
            {synthetic ? (
              <>
                <div className="notice subtle">
                  <Icon name="help" size={14} />
                  <span>Only use synthetic questions. A file label cannot detect confidential information in typed text.</span>
                </div>
                <button className="button secondary full-width" onClick={() => void classify('restricted')} disabled={busy}>
                  Restrict this dataset
                </button>
              </>
            ) : (
              <>
                <div className="notice subtle">
                  <Icon name="warning" size={14} />
                  <span>Only enable cloud AI if this file is synthetic demo data. Confidential company records should remain restricted.</span>
                </div>
                <label className="checkbox-label">
                  <input type="checkbox" checked={privacyAck} onChange={e => setPrivacyAck(e.target.checked)} />
                  <span>I confirm this dataset is synthetic and safe to send to the cloud model API.</span>
                </label>
                <button
                  className="button primary full-width"
                  onClick={() => void classify('synthetic')}
                  disabled={!privacyAck || busy}
                >
                  <Icon name="spark" size={15} />
                  <span>Enable synthetic demo mode</span>
                </button>
              </>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
