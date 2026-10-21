(() => {
  const $ = id => document.getElementById(id);
  const css = v => getComputedStyle(document.body).getPropertyValue(v).trim();
  const [black, white, start, end, font, text] = ['--black', '--white', '--start', '--end', '--font', '--text'].map(css);
  let state = { nodes: [], max_level: 2, solution: null }, selected = null, busy = '', timer;
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);
  const url = (...p) => '/api/nodes' + p.map(x => '/' + encodeURIComponent(x)).join('');
  const node = id => state.nodes.find(n => n.id === id);
  const name = id => node(id)?.name.trim() || 'UNNAMED NODE';
  const fixed = n => n?.role === 'start' || n?.role === 'finish';

  function toast(msg, error = true) {
    clearTimeout(timer);
    Object.assign($('toast'), { textContent: msg, hidden: false, className: error ? 'error' : '' });
    timer = setTimeout(() => { $('toast').hidden = true; }, 4000);
  }

  async function api(path, method = 'GET', body) {
    try {
      const res = await fetch(path, { method, cache: 'no-store', headers: { 'Content-Type': 'application/json' }, body: body && JSON.stringify(body) });
      const data = await res.json();
      if (data.state) { state = data.state; if (!node(selected) || fixed(node(selected))) selected = null; render(); }
      if (res.ok) return data;
      toast(data.error || 'The request could not be completed.');
    } catch { toast('Could not reach the server. Check the connection and retry.'); }
    return null;
  }

  /* ---- node cards ---- */
  const card = (n, i) => {
    const d = `data-id="${esc(n.id)}"`;
    const level = n.role === 'start' ? 'Level 0' : n.role === 'finish' ? 'Last level' : `Level ${n.level ?? 1}`;
    const chips = n.edges.map(e => `<span>${esc(name(e.to))} · ${esc(e.weight)} <button type="button" data-do="unlink" ${d} data-to="${esc(e.to)}" aria-label="Remove connection">×</button></span>`).join('') || 'No connections';
    const options = state.nodes.filter(o => o.id !== n.id).map(o => `<option value="${esc(o.id)}">${esc(o.name.trim() || '(unnamed)')}</option>`).join('');
    const role = n.role ? `<select disabled><option>${n.role === 'start' ? 'Start' : 'Destination'} (fixed)</option></select>`
      : `<select data-do="role" ${d}><option value="">Regular</option><option value="start">Start</option><option value="finish">Destination</option></select>`;
    return `<article class="${n.role}"><h3>${i + 1}. ${esc(n.name.trim() || 'Unnamed')} <small>${level}</small>
        ${state.nodes.length > 2 ? `<button type="button" data-do="delete" ${d} aria-label="Delete node">×</button>` : ''}</h3>
      <input data-do="name" ${d} value="${esc(n.name)}" maxlength="24" placeholder="Node name" aria-label="Node name">${role}
      <div>${chips}</div>
      <form ${d}><select name="to" aria-label="Destination">${options}</select><input name="weight" type="number" min="0" step="any" value="1" aria-label="Weight"><button>+</button></form></article>`;
  };

  /* ---- graph (Cytoscape draws nodes, edges, arrows and labels) ---- */
  const label = { 'font-family': font, 'font-size': text, color: black };
  const cy = cytoscape({ container: $('graph'), autoungrabify: true, boxSelectionEnabled: false, maxZoom: 1.2, style: [
    { selector: 'node', style: { ...label, shape: 'rectangle', label: 'data(label)', width: 'label', height: 44, padding: 14, 'text-valign': 'center', 'background-color': white, 'border-width': 2, 'border-color': black } },
    { selector: 'node.start', style: { 'border-color': start, 'border-width': 4 } },
    { selector: 'node.finish', style: { 'border-color': end, 'border-width': 4 } },
    { selector: 'node.path', style: { 'border-width': 4 } },
    { selector: 'node:selected', style: { 'border-style': 'dashed', 'border-width': 4 } },
    { selector: 'edge', style: { ...label, 'curve-style': 'bezier', 'target-arrow-shape': 'triangle', width: 2, label: 'data(weight)', 'line-color': black, 'target-arrow-color': black, 'text-background-color': white, 'text-background-opacity': 1, 'text-background-padding': 3 } },
    { selector: 'edge.same', style: { 'curve-style': 'unbundled-bezier', 'control-point-distances': [90], 'control-point-weights': [0.5] } },
    { selector: 'edge.path', style: { width: 5 } },
    { selector: '.dim', style: { opacity: 0.25 } }] });

  function drawGraph() {
    const nodes = state.nodes.filter(n => n.name.trim()), ids = new Set(nodes.map(n => n.id));
    const last = Math.max(2, +state.max_level || 2), sol = state.solution?.reachable ? state.solution : null, path = sol?.pathIds || [];
    const level = n => n.role === 'start' ? 0 : n.role === 'finish' ? last : Math.min(last - 1, Math.max(1, +n.level || 1));
    const hot = new Set(path.slice(1).map((id, i) => `${path[i]}>${id}`));
    const cols = Array.from({ length: last + 1 }, () => []);
    nodes.forEach(n => cols[level(n)].push(n));
    const els = cols.flatMap((col, x) => col.map((n, y) => ({ data: { id: n.id, label: n.name.trim() }, position: { x: x * 220, y: (y - (col.length - 1) / 2) * 90 },
      classes: [n.role, path.includes(n.id) && 'path', sol && !path.includes(n.id) && 'dim'].filter(Boolean).join(' ') })));
    nodes.forEach(s => s.edges.filter(e => ids.has(e.to)).forEach(e => els.push({ data: { id: `${s.id}>${e.to}`, source: s.id, target: e.to, weight: e.weight },
      classes: [level(s) === level(node(e.to)) && 'same', hot.has(`${s.id}>${e.to}`) ? 'path' : sol && 'dim'].filter(Boolean).join(' ') })));
    cy.batch(() => { cy.elements().remove(); cy.add(els); });
    if (selected) cy.getElementById(selected).select();
    cy.resize(); cy.fit(undefined, 40);
  }
  cy.on('tap', 'node', e => {
    const n = node(e.target.id());
    selected = fixed(n) ? null : n.id;
    if (fixed(n)) { e.target.unselect(); toast(`The ${n.role === 'start' ? 'start' : 'destination'} node is locked in place.`, false); }
    panels();
  });
  cy.on('tap', e => { if (e.target === cy) { selected = null; panels(); } });

  /* ---- panels & render ---- */
  function panels() {
    const n = node(selected), sol = state.solution;
    $('levelMovePanel').hidden = !n;
    if (n) {
      $('selectedNodeName').textContent = n.name.trim() || 'UNNAMED NODE';
      $('selectedNodeLevel').textContent = `Level ${n.level ?? 1}`;
      $('moveLeftButton').disabled = busy === 'move' || Number(n.level) <= 1;
      $('moveRightButton').disabled = busy === 'move';
    }
    $('solutionCard').hidden = !sol;
    if (sol) {
      $('solutionValue').textContent = sol.reachable ? `Total cost: ${sol.cost}` : 'No route found';
      $('solutionPath').textContent = sol.reachable ? sol.pathNames.join(' → ') : sol.message || 'No path connects start and destination.';
    }
  }

  function render() {
    $('nodeCount').textContent = `${state.nodes.length} nodes`;
    $('nodeCards').innerHTML = state.nodes.map(card).join('') + `<button type="button" data-do="add" aria-label="Add node" ${busy === 'add' || state.nodes.length >= 40 ? 'disabled' : ''}>+</button>`;
    $('solveButton').disabled = busy === 'solve';
    $('solveLabel').textContent = busy === 'solve' ? 'SOLVING…' : 'SOLVE';
    drawGraph(); panels();
  }

  /* ---- events ---- */
  const cards = $('nodeCards');
  cards.addEventListener('change', e => {
    const { do: act, id } = e.target.dataset;
    if (act === 'name' || act === 'role') api(url(id), 'PATCH', { [act]: e.target.value });
  });
  cards.addEventListener('submit', e => {
    e.preventDefault();
    const f = e.target, w = f.weight.value;
    if (w === '' || !isFinite(w) || Number(w) < 0) return toast('Enter a weight of zero or more.');
    api(url(f.dataset.id, 'edges'), 'POST', { to: f.to.value, weight: Number(w) });
  });
  cards.addEventListener('click', async e => {
    const b = e.target.closest('button[data-do]');
    if (!b) return;
    const { do: act, id, to } = b.dataset;
    if (act === 'delete' && confirm(`Delete “${name(id)}” and all its connections?`)) api(url(id), 'DELETE');
    if (act === 'unlink') api(url(id, 'edges', to), 'DELETE');
    if (act === 'add' && !busy) {
      busy = 'add'; render();
      const ok = await api(url(), 'POST', {});
      busy = ''; render();
      if (ok) { cards.scrollTo({ left: cards.scrollWidth, behavior: 'smooth' }); setTimeout(() => cards.querySelector('article:last-of-type input')?.focus(), 160); }
    }
  });
  $('solveButton').onclick = async () => {
    if (busy) return;
    busy = 'solve'; render();
    const data = await api('/api/solve', 'POST', {});
    busy = ''; render();
    const s = data?.state?.solution;
    if (s) toast(s.reachable ? 'Shortest path calculated.' : s.message, !s.reachable);
  };
  [['moveLeftButton', 'left'], ['moveRightButton', 'right']].forEach(([id, direction]) => $(id).onclick = async () => {
    const sel = selected;
    if (!sel || busy) return;
    busy = 'move'; panels();
    await api(url(sel, 'level'), 'POST', { direction });
    busy = ''; panels();
  });
  api('/api/state');
})();