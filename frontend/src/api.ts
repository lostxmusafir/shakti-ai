let csrf = '';
export function setCSRF(value:string){csrf=value;}
export async function api<T>(path:string, options:RequestInit={}):Promise<T>{
  const headers = new Headers(options.headers);
  if(options.body && !(options.body instanceof FormData)) headers.set('Content-Type','application/json');
  if(options.method && !['GET','HEAD'].includes(options.method.toUpperCase()) && csrf) headers.set('X-CSRF-Token',csrf);
  const response = await fetch(`/api${path}`,{...options,headers,credentials:'same-origin'});
  const data = await response.json().catch(()=>null);
  if(!response.ok){
    const detail = data?.detail;
    const message = typeof detail==='string'?detail:Array.isArray(detail)?detail.map((x:{msg:string})=>x.msg).join('; '):data?.message || `Request failed (${response.status}).`;
    throw new Error(message);
  }
  return data as T;
}
export const post = <T>(path:string,body:unknown={})=>api<T>(path,{method:'POST',body:JSON.stringify(body)});
export const errorText = (e:unknown) => e instanceof Error ? e.message : 'Something went wrong. Please try again.';
