const el = (id) => document.getElementById(id);
let current = null;
let busy = false;
function collection() {
  const name = el('collection').value;
  if (!/^[a-z0-9-]{1,48}$/.test(name)) throw Error('Choose a valid collection name.');
  return name;
}
async function api(path, body, method = 'POST') {
  const headers = { Authorization: `Bearer ${el('token').value}` };
  if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const res = await fetch(path, { method, headers,
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined });
  if (!res.ok) {
    const error = await res.json();
    throw Error(typeof error.detail === 'string' ? error.detail : 'Check the request fields.');
  }
  return res;
}
async function action(message, fn) {
  if (busy) return;
  busy = true;
  el('status').textContent = message;
  for (const id of ['upload', 'ask', 'approve', 'export']) el(id).disabled = true;
  try { await fn(); } catch (error) { el('status').textContent = error.message; }
  finally {
    busy = false;
    el('upload').disabled = false;
    el('ask').disabled = false;
    el('approve').disabled = current?.status !== 'pending_review';
    el('export').disabled = current?.status !== 'approved';
  }
}
function render(run) {
  current = run;
  el('result').hidden = false;
  el('run-status').textContent = run.status.replaceAll('_', ' ');
  el('claims').replaceChildren(); el('sources').replaceChildren(); el('stages').replaceChildren();
  for (const event of run.events) {
    const item = document.createElement('li'); item.textContent = event.stage.replaceAll('_', ' '); el('stages').append(item);
  }
  for (const claim of run.claims) {
    const item = document.createElement('div'); item.className = 'claim';
    item.textContent = claim.quote;
    const source = document.createElement('small'); source.textContent = `${claim.document} · page ${claim.page} · ${claim.source_id}`;
    item.append(source); el('claims').append(item);
  }
  for (const source of run.sources) {
    const item = document.createElement('div'); item.className = 'source';
    item.textContent = source.text;
    const label = document.createElement('small'); label.textContent = `${source.document} · page ${source.page} · cosine ${source.score}`;
    item.append(label); el('sources').append(item);
  }
  el('angle').textContent = run.suggested_angle ? `Suggested angle — requires review: ${run.suggested_angle}` : '';
  el('timing').textContent = `${run.latency_ms} ms · ${run.provider} · ${run.id}`;
  el('status').textContent = run.status === 'approved' ? 'Evidence snapshot approved. You can download the reviewed brief.' : run.reason;
}
el('upload').onclick = () => action('Indexing document; the embedding model may initialize on first use…', async () => {
  if (!el('file').files.length) throw Error('Select a document first.');
  const data = new FormData(); data.append('file', el('file').files[0]);
  const result = await (await api(`/v1/collections/${collection()}/upload`, data)).json();
  el('status').textContent = `Indexed ${result.chunks} source chunks. Ask a question below.`;
});
el('ask').onclick = () => action('Retrieving source evidence…', async () => {
  current = null; el('result').hidden = true; el('note').value = '';
  const run = await (await api(`/v1/collections/${collection()}/runs`, {
    question: el('question').value, provider: el('provider').value, cloud_consent: el('consent').checked })).json();
  render(run);
});
el('approve').onclick = () => action('Saving your review…', async () => {
  render(await (await api(`/v1/runs/${current.id}/approve`, {
    evidence_sha256: current.evidence_sha256, note: el('note').value })).json());
});
el('export').onclick = () => action('Preparing reviewed brief…', async () => {
  const file = await (await api(`/v1/runs/${current.id}/export`, null, 'GET')).blob();
  const url = URL.createObjectURL(file); const a = document.createElement('a');
  a.href = url; a.download = 'reviewed-brief.md'; a.click(); URL.revokeObjectURL(url);
  el('status').textContent = 'Reviewed brief downloaded.';
});
