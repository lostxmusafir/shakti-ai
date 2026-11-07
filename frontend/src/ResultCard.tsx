import { useState } from 'react';
import type { Result } from './types';
import { Icon } from './Icons';

export default function ResultCard({result, onRetry}:{result:Result; onRetry?:()=>void}){
 const [copied, setCopied] = useState(false);
 const [showEvidence, setShowEvidence] = useState(false);

 function copyAnswer(){
   const text = `${result.answer}\n\nCalculation: ${result.method}\nTable: ${result.table_name || 'Selected table'} (${result.row_count || 0} rows included)`;
   navigator.clipboard.writeText(text).then(()=>{
     setCopied(true);
     setTimeout(()=>setCopied(false), 2000);
   }).catch(()=>{});
 }

 return <article className="result-card">
  <div className="result-label">
   <div className="result-author">
     <span className="clone-spark-icon" aria-hidden="true">✳</span>
     <strong>Zydrakon AI</strong>
   </div>
   <span className="verified-tag"><Icon name="check" size={12}/>Calculated locally</span>
  </div>

  <p className="answer-text">{result.answer}</p>

  {result.rows?.length>0 && result.columns?.length>0 && <div className="result-table-wrap">
   <table className="result-table">
     <thead><tr>{result.columns.map((c,i)=><th key={`${c}-${i}`}>{c}</th>)}</tr></thead>
     <tbody>{result.rows.slice(0,25).map((r,i)=><tr key={i}>{r.map((c,j)=><td key={j}>{c===null?<span className="null-value">—</span>:String(c)}</td>)}</tr>)}</tbody>
   </table>
   {result.rows.length>25&&<p className="table-caption">Showing 25 of {result.rows.length} returned rows.</p>}
  </div>}

  <div className="result-foot">
   <span><Icon name="file" size={13}/>{result.table_name||'Selected table'}</span>
   <span>{result.row_count?.toLocaleString()} rows included</span>
  </div>

  <div className="result-actions-bar">
   <button className="action-pill" onClick={copyAnswer} title="Copy answer to clipboard">
     <Icon name={copied ? "check" : "file"} size={13}/>
     <span>{copied ? "Copied" : "Copy"}</span>
   </button>
   <button className="action-pill" onClick={()=>setShowEvidence(!showEvidence)}>
     <Icon name="eye" size={13}/>
     <span>{showEvidence ? "Hide evidence" : "Calculation & evidence"}</span>
   </button>
   {onRetry && <button className="action-pill" onClick={onRetry} title="Recalculate">
     <Icon name="refresh" size={13}/>
     <span>Retry</span>
   </button>}
  </div>

  {showEvidence && <div className="evidence-body">
   <dl>
     <dt>Method</dt><dd>{result.method}</dd>
     <dt>Dataset</dt><dd>{result.dataset_name||'Current dataset'} {result.version?`· version ${result.version}`:''}</dd>
     <dt>Excluded rows</dt><dd>{result.excluded_rows?.toLocaleString()||0}</dd>
     <dt>Filters</dt><dd>{result.filters?.length?result.filters.map((f,i)=><span className="evidence-filter" key={i}>{f.column} {f.op} {Array.isArray(f.value)?f.value.join(', '):String(f.value??'')}</span>):'No filters applied'}</dd>
     <dt>Source rows</dt><dd className="source-rows">{result.source_rows?.join(', ')||'None'}</dd>
   </dl>
  </div>}

  {result.warnings?.map((w,i)=><div key={i} className="result-warning"><Icon name="warning" size={14}/>{w}</div>)}
 </article>;
}
