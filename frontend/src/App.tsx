import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api, post, setCSRF, errorText } from './api';
import type { Auth, Cell, Dataset, Job, Message, Plan, Preview, Settings } from './types';
import { Brand, Icon } from './Icons';
import AuthView from './AuthView';
import Calculator from './Calculator';
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
  const [showData, setShowData] = useState(true);
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
  const [mode, setMode] = useState<'chat' | 'calculate'>('chat');
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);
  const [jobStatus, setJobStatus] = useState('');
  const [failedJob, setFailedJob] = useState<(ActiveJob & { error: string }) | null>(null);

  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; kind: 'error' | 'success' } | null>(null);
  const [edits, setEdits] = useState<Record<number, Cell[]>>({});
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [dragging, setDragging] = useState(false);

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
            setNotice({ kind: 'success', text: 'File processed. Review the data before analysing.' });
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
    setEdits({});
    setFailedJob(null);
    setShowData(true);
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

  async function confirmTable() {
    if (!preview || !selectedId) return;
    setConfirmBusy(true);
    try {
      let rows: Cell[][] | undefined;
      if (Object.keys(edits).length) {
        rows = [];
        for (let start = 0; start < preview.total_rows; start += 100) {
          const chunk = await api<Preview>(`/datasets/${selectedId}/preview?table_index=${tableIndex}&offset=${start}&limit=100`);
          if (chunk.version !== preview.version) throw new Error('This dataset changed. Refresh and review the latest version.');
          chunk.table.rows.forEach((r, i) => rows!.push(edits[start + i] ?? r));
        }
      }
      await post(`/datasets/${selectedId}/confirm`, { table_index: tableIndex, version: preview.version, ...(rows ? { rows } : {}) });
      setEdits({});
      setRefresh(x => x + 1);
      setNotice({ kind: 'success', text: 'Table confirmed. You can now run calculations.' });
    } catch (e) {
      setNotice({ text: errorText(e), kind: 'error' });
    } finally {
      setConfirmBusy(false);
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

  async function removeDataset() {
    if (!selected) return;
    if (!window.confirm(`Delete “${selected.name}”? Its source file, derived data and conversations will be removed.`)) return;
    setBusy(true);
    try {
      await api(`/datasets/${selected.id}`, { method: 'DELETE' });
      setSelectedId('');
      setPreview(null);
      setRefresh(x => x + 1);
    } catch (e) {
      setNotice({ kind: 'error', text: errorText(e) });
    } finally {
      setBusy(false);
    }
  }

  async function ask(e?: FormEvent) {
    e?.preventDefault();
    if (!question.trim() || !selectedId || activeJob || busy || !preview) return;
    const qText = question.trim();
    setQuestion('');
    setBusy(true);
    setNotice(null);
    try {
      let currentVersion = preview.version;
      if (!confirmed) {
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

  async function submitAnalysis(endpoint: string, body: unknown, label: string) {
    if (activeJob || busy) return;
    setBusy(true);
    setFailedJob(null);
    try {
      const r = await post<{ job_id: string }>(endpoint, body);
      setJobStatus('queued');
      setActiveJob({ id: r.job_id, kind: 'analysis', dataset_id: selectedId, question: label });
    } catch (e) {
      setNotice({ kind: 'error', text: errorText(e) });
    } finally {
      setBusy(false);
    }
  }

  function calculate(plan: Plan, label: string) {
    if (!preview) return;
    void submitAnalysis('/analyses', { dataset_id: selectedId, table_index: tableIndex, version: preview.version, plan }, label);
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

  function editCell(row: number, col: number, value: string) {
    if (!preview) return;
    setEdits(prev => {
      const cells = [...(prev[row] ?? preview.table.rows[row - offset])];
      cells[col] = value === '' ? null : value;
      return { ...prev, [row]: cells };
    });
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
    <div className={`app-shell ${pinned ? 'pinned' : 'unpinned'} ${!showData && confirmed ? 'chat-focus' : ''}`}>
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
            setShowData(true);
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
              <button
                key={d.id}
                className={`dataset-link ${d.id === selectedId ? 'selected' : ''}`}
                onClick={() => selectDataset(d.id)}
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
                {d.classification === 'synthetic' ? (
                  <span className="tiny-dot synthetic" title="Synthetic data" />
                ) : (
                  <Icon name="lock" size={12} />
                )}
              </button>
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

      {/* Main Container */}
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <span className="clone-spark" style={{ fontSize: '18px', marginRight: '6px' }}>✳</span>
            <span>Zydrakon</span>
            <Icon name="chevron" size={12} />
            <strong>{selected ? selected.name : 'Workspace'}</strong>
          </div>
          <div className="topbar-right">
            {selected && (
              <button
                className="button secondary small-button clone-data-toggle"
                onClick={() => setShowData(!showData)}
                disabled={!confirmed}
                title="Toggle between split-view and focused chat"
              >
                <Icon name="columns" size={14} />
                <span>{showData ? 'Focus on chat' : 'Show data preview'}</span>
              </button>
            )}
            <span className="pilot-badge">EXCEL COPILOT</span>
            <button className="connection-state" onClick={() => setShowSettings(true)}>
              <span className={`status-dot ${cloudReady ? 'online' : 'offline'}`} />
              <span>{cloudReady ? 'Cloud AI Ready' : 'Local Calculations'}</span>
              <Icon name="down" size={11} />
            </button>
          </div>
        </header>

        <main className={`workspace-main ${!selected && !activeJob ? 'clone-home-view' : ''}`}>
          {!selected && !activeJob && (
            <CloneHome
              username={auth.user.username}
              draft={question}
              setDraft={setQuestion}
              onUpload={() => fileRef.current?.click()}
              onSample={() => void loadSample()}
              busy={busy}
              hasDatasets={datasets.length > 0}
              onSubmitDraft={() => {
                if (datasets[0]) {
                  selectDataset(datasets[0].id);
                }
              }}
            />
          )}

          {/* Heading when dataset active */}
          {selected && (
            <div className="page-heading">
              <div>
                <div className="eyebrow">COMPANY DATA ASSISTANT / {selected.name.toUpperCase()}</div>
                <h1>{selected.name}</h1>
                <p>Explore columns, verify calculations, and inspect source evidence.</p>
              </div>
              <button
                className="button primary"
                onClick={() => fileRef.current?.click()}
                disabled={busy || !!activeJob}
              >
                <Icon name="plus" size={15} />
                <span>Upload new file</span>
              </button>
            </div>
          )}

          <div className="workspace-grid">
            {/* Center Data Panel */}
            <section className="data-panel">
              <div className="panel-heading">
                <div>
                  <span className="panel-icon"><Icon name="columns" size={18} /></span>
                  <div>
                    <h2>Data preview</h2>
                    <span>{selected ? 'Inspect the table powering calculations' : 'No file selected'}</span>
                  </div>
                </div>
                {selected && (
                  <button
                    className="icon-button"
                    onClick={() => void removeDataset()}
                    disabled={busy || !!activeJob}
                    aria-label="Delete dataset"
                    title="Delete dataset"
                  >
                    <Icon name="trash" size={16} />
                  </button>
                )}
              </div>

              {!selected ? (
                <div
                  className={`upload-empty ${dragging ? 'dragging' : ''}`}
                  onDragOver={e => {
                    e.preventDefault();
                    setDragging(true);
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={e => {
                    e.preventDefault();
                    setDragging(false);
                    if (e.dataTransfer.files[0]) void upload(e.dataTransfer.files[0]);
                  }}
                >
                  <span className="clone-spark" style={{ fontSize: '38px', color: '#B6613C' }}>✳</span>
                  <h3>Start with your data</h3>
                  <p>Drop a CSV, Excel (.xlsx) file, or clear table screenshot here.<br />Calculations run deterministically on the full dataset.</p>
                  <button className="button primary" onClick={() => fileRef.current?.click()} disabled={busy || !!activeJob}>
                    <Icon name="upload" size={16} />
                    <span>Choose file from computer</span>
                  </button>
                  <div className="file-formats">
                    <span>CSV</span>
                    <span>XLSX</span>
                    <span>PNG / JPG</span>
                  </div>
                </div>
              ) : (
                <>
                  <div className="dataset-toolbar">
                    <div className="current-file">
                      <span className="file-symbol">
                        <Icon name={fileIsImage(selected.name) ? 'image' : 'file'} size={18} />
                      </span>
                      <div>
                        <strong title={selected.name}>{selected.name}</strong>
                        <span>
                          {preview
                            ? `${preview.total_rows.toLocaleString()} rows · ${preview.table.columns.length} columns · v${preview.version}`
                            : 'Preparing dataset'}
                        </span>
                      </div>
                    </div>
                    <button
                      className={`classification-pill ${synthetic ? 'synthetic' : 'restricted'}`}
                      onClick={() => {
                        setPrivacyAck(false);
                        setShowPrivacy(true);
                      }}
                      disabled={busy || !!activeJob}
                    >
                      <Icon name={synthetic ? 'spark' : 'lock'} size={12} />
                      <span>{synthetic ? 'Synthetic demo' : 'Restricted (Default)'}</span>
                      <Icon name="down" size={11} />
                    </button>
                  </div>

                  {['queued', 'running'].includes(selected.status) ? (
                    <div className="panel-empty">
                      <span className="spinner dark" />
                      <h3>Reading and parsing file…</h3>
                      <p>Running local ingestion worker.</p>
                    </div>
                  ) : selected.status === 'failed' ? (
                    <div className="panel-empty">
                      <span className="error-circle"><Icon name="warning" size={24} /></span>
                      <h3>This file needs attention</h3>
                      <p>{selected.error || 'The file could not be processed.'}</p>
                      {selected.job_id && (
                        <button className="button secondary" onClick={() => void retry(selected.job_id!, 'upload')} disabled={busy || !!activeJob}>
                          <Icon name="refresh" size={14} />
                          <span>Retry processing</span>
                        </button>
                      )}
                    </div>
                  ) : previewLoading ? (
                    <div className="panel-empty">
                      <span className="spinner dark" />
                      <p>Loading table…</p>
                    </div>
                  ) : previewError ? (
                    <div className="panel-empty">
                      <Icon name="warning" size={20} />
                      <p>{previewError}</p>
                      <button className="button secondary" onClick={() => setRefresh(x => x + 1)}>Reload preview</button>
                    </div>
                  ) : preview ? (
                    <>
                      <div className="table-tabs" role="tablist" aria-label="Workbook sheets">
                        {preview.table_names.map((name, i) => (
                          <button
                            role="tab"
                            aria-selected={tableIndex === i}
                            key={`${name}-${i}`}
                            className={tableIndex === i ? 'active' : ''}
                            onClick={() => {
                              setTableIndex(i);
                              setOffset(0);
                              setEdits({});
                            }}
                          >
                            <Icon name="grid" size={13} />
                            <span>{name}</span>
                          </button>
                        ))}
                        <span className={`table-review-state ${confirmed ? 'confirmed' : ''}`}>
                          <Icon name={confirmed ? 'check' : 'eye'} size={12} />
                          <span>{confirmed ? 'Reviewed' : 'Review needed'}</span>
                        </span>
                      </div>

                      {preview.table.warnings.length > 0 && (
                        <details className="data-warnings">
                          <summary>
                            <Icon name="warning" size={14} />
                            <span>{preview.table.warnings.length} data {preview.table.warnings.length === 1 ? 'note' : 'notes'} to review</span>
                            <Icon name="down" size={12} />
                          </summary>
                          <ul>
                            {preview.table.warnings.map((w, i) => <li key={i}>{w}</li>)}
                          </ul>
                        </details>
                      )}

                      {preview.table.requires_review && (
                        <details className="image-preview">
                          <summary>
                            <Icon name="image" size={14} />
                            <span>View original uploaded image</span>
                            <Icon name="down" size={12} />
                          </summary>
                          <img src={`/api/datasets/${selectedId}/image`} alt="Original table upload" />
                        </details>
                      )}

                      {!confirmed && (
                        <div className="review-banner">
                          <Icon name="eye" size={16} />
                          <div>
                            <strong>{preview.table.requires_review ? 'Inspect extracted table cells' : 'Review table before calculation'}</strong>
                            <span>{preview.table.requires_review ? 'Correct any OCR misreads in the inputs below, then confirm.' : 'Calculations will execute deterministically across all rows.'}</span>
                          </div>
                        </div>
                      )}

                      <div className="data-table-scroll">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th className="row-number" scope="col">#</th>
                              {preview.table.columns.map((c, i) => (
                                <th key={`${c.name}-${i}`} scope="col">
                                  <span className="column-type">{c.formula ? 'ƒ' : c.type === 'number' ? '#' : c.type === 'date' ? '◷' : 'Aa'}</span>
                                  <span>{c.name}</span>
                                  {c.formula && <span className="formula-mark" title="Formula values are not recalculated">!</span>}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {preview.table.rows.map((r, i) => (
                              <tr key={offset + i}>
                                <th scope="row" className="row-number">{preview.table.source_rows?.[i] ?? offset + i + 2}</th>
                                {(edits[offset + i] ?? r).map((c, j) => (
                                  <td
                                    key={j}
                                    className={`${preview.table.columns[j]?.type === 'number' ? 'numeric' : ''} ${preview.table.columns[j]?.formula ? 'formula-cell' : ''}`}
                                  >
                                    {preview.table.requires_review && !confirmed ? (
                                      <input
                                        className="cell-input"
                                        aria-label={`Row ${offset + i + 1}, ${preview.table.columns[j]?.name}`}
                                        value={c === null ? '' : String(c)}
                                        onChange={e => editCell(offset + i, j, e.target.value)}
                                      />
                                    ) : c === null ? (
                                      <span className="null-value">—</span>
                                    ) : (
                                      String(c)
                                    )}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {preview.table.rows.length === 0 && <p className="no-rows">This table has no rows.</p>}
                      </div>

                      <div className="table-footer">
                        <span>
                          {preview.total_rows ? `${offset + 1}–${Math.min(offset + preview.table.rows.length, preview.total_rows)}` : '0'} of {preview.total_rows.toLocaleString()} rows
                        </span>
                        <div>
                          <button
                            className="icon-button prev-page"
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

                      {!confirmed ? (
                        <div className="confirm-footer">
                          <span><Icon name="shield" size={14} />Original file remains immutable</span>
                          <button
                            className="button primary small-button"
                            onClick={() => void confirmTable()}
                            disabled={confirmBusy || busy || !!activeJob}
                          >
                            {confirmBusy ? <span className="spinner" /> : <Icon name="check" size={15} />}
                            <span>Confirm table</span>
                          </button>
                        </div>
                      ) : (
                        <div className="confirmed-footer">
                          <Icon name="check" size={14} />
                          <span>Table reviewed. All {preview.total_rows.toLocaleString()} rows verified for calculations.</span>
                        </div>
                      )}
                    </>
                  ) : null}
                </>
              )}
            </section>

            {/* Right Analysis Panel */}
            <section className="analysis-panel">
              <div className="panel-heading">
                <div>
                  <span className="panel-icon"><Icon name="spark" size={18} /></span>
                  <div>
                    <h2>Conversation & Analysis</h2>
                    <span>Evidence-backed answers</span>
                  </div>
                </div>
                <div className="mode-switch" role="tablist" aria-label="Analysis mode">
                  <button
                    role="tab"
                    aria-selected={mode === 'chat'}
                    className={mode === 'chat' ? 'active' : ''}
                    onClick={() => setMode('chat')}
                  >
                    <Icon name="spark" size={13} />
                    <span>Ask AI</span>
                  </button>
                  <button
                    role="tab"
                    aria-selected={mode === 'calculate'}
                    className={mode === 'calculate' ? 'active' : ''}
                    onClick={() => setMode('calculate')}
                  >
                    <Icon name="calculator" size={13} />
                    <span>Calculate</span>
                  </button>
                </div>
              </div>

              <div className="conversation" aria-live="polite">
                {messages.length === 0 && !activeJob ? (
                  <div className="assistant-empty">
                    <span className="clone-spark-icon" style={{ fontSize: '32px', color: '#B6613C' }}>✳</span>
                    <h3>{mode === 'chat' ? 'Copilot in Excel — Ask anything about your data' : 'Run deterministic calculations'}</h3>
                    <p>
                      {mode === 'chat'
                        ? 'Ask for totals, trends, Excel formulas, summaries, or anomalies. Copilot analyzes your full spreadsheet directly.'
                        : 'Choose an aggregation operation, column, and filters. Results compute locally on the full table.'}
                    </p>
                    {mode === 'chat' && (
                      <div className="question-suggestions">
                        <span>EXAMPLE QUESTIONS (ENGLISH & HINGLISH)</span>
                        {['What is the total sales amount?', 'Show the top 5 records by revenue', 'Sabse zyada incidents kis port par hain?', 'Identify duplicate entries and missing blanks'].map(q => (
                          <button
                            key={q}
                            disabled={!canAsk}
                            onClick={() => {
                              setQuestion(q);
                              questionRef.current?.focus();
                            }}
                          >
                            <span>{q}</span>
                            <Icon name="arrow" size={13} />
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  messages.map(m => (
                    <div className="conversation-turn" key={m.id}>
                      <div className="user-question">
                        <span className="user-badge">You</span>
                        <p>{m.question}</p>
                      </div>
                      {m.result && <ResultCard result={m.result} />}
                    </div>
                  ))
                )}

                {activeJob?.kind === 'analysis' && activeJob.dataset_id === selectedId && (
                  <div className="conversation-turn">
                    <div className="user-question">
                      <span className="user-badge">You</span>
                      <p>{activeJob.question}</p>
                    </div>
                    <div className="working-message">
                      <span className="spinner dark" />
                      <div>
                        <strong>{jobStatus === 'queued' ? 'Queued for calculation…' : 'Calculating on full dataset…'}</strong>
                        <span>Validating plan and running Python Decimal / pandas.</span>
                      </div>
                    </div>
                  </div>
                )}

                {failedJob && failedJob.dataset_id === selectedId && (
                  <div className="job-error" role="alert">
                    <Icon name="warning" size={16} />
                    <div>
                      <strong>Could not complete this analysis</strong>
                      <p>{failedJob.error}</p>
                      <button
                        className="text-button"
                        onClick={() => void retry(failedJob.id, failedJob.kind, failedJob.question)}
                        disabled={busy || !!activeJob}
                      >
                        <Icon name="refresh" size={13} />
                        <span>Retry</span>
                      </button>
                    </div>
                  </div>
                )}

                <div ref={messagesEnd} />
              </div>

              {/* Composer */}
              {mode === 'chat' ? (
                <div className="composer-section">
                  {!canAsk && (
                    <div className="composer-gate">
                      <Icon name="lock" size={15} />
                      <div>
                        {!selected ? (
                          'Upload a dataset to start asking questions.'
                        ) : !ready ? (
                          'Preparing file…'
                        ) : !cloudReady ? (
                          <>
                            <strong>Cloud API key not configured.</strong>
                            <button className="text-button" onClick={() => setMode('calculate')}>
                              Use local calculation builder
                            </button>
                          </>
                        ) : (
                          'Ready'
                        )}
                      </div>
                    </div>
                  )}

                  <form className={`question-composer ${!canAsk ? 'disabled' : ''}`} onSubmit={e => void ask(e)}>
                    <textarea
                      ref={questionRef}
                      aria-label="Ask a question about your data"
                      placeholder={canAsk ? 'Ask in English or Hinglish (e.g. Sabse zyada incidents kis port par hain?)' : 'Review table or configure cloud key to ask…'}
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
                    <div className="composer-bottom">
                      <span className="composer-sheet-name">
                        <Icon name="file" size={12} />
                        <span>{preview?.table.name || 'No table selected'}</span>
                      </span>
                      <button
                        aria-label="Send question"
                        className="send-button"
                        disabled={!canAsk || !question.trim() || busy || !!activeJob}
                      >
                        <Icon name="arrow" size={16} />
                      </button>
                    </div>
                  </form>
                </div>
              ) : (
                <div className="calculator-section">
                  {!confirmed && (
                    <div className="composer-gate">
                      <Icon name="eye" size={15} />
                      <span>{selected ? 'Confirm table to run local calculations.' : 'Upload and confirm a table first.'}</span>
                    </div>
                  )}
                  <Calculator
                    key={`${selectedId}-${tableIndex}`}
                    columns={preview?.table.columns || []}
                    disabled={!ready || !confirmed}
                    busy={busy || !!activeJob}
                    onRun={calculate}
                  />
                </div>
              )}
            </section>
          </div>
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
