(() => {
  'use strict';
  const E = Object.fromEntries([...document.querySelectorAll('[id]')].map(e => [e.id, e]));
  const { nodeCards, nodeCount, graphCanvas, graphSvg: svg, levelMovePanel: movePanel, selectedNodeName, selectedNodeLevel,
          moveLeftButton: leftBtn, moveRightButton: rightBtn, solutionCard, solutionValue, solutionPath, toast, solveButton, solveLabel } = E;
  const panel = graphCanvas.parentElement; // fixed-size parent: measuring it avoids scrollbar resize loops
  let state = { nodes: [], max_level: 2, solution: null }, selectedId = null, busy = '', toastTimer;
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);
  const enc = encodeURIComponent, getNode = id => state.nodes.find(n => n.id === id);
  const nameOf = id => getNode(id)?.name?.trim() || 'UNNAMED NODE';
  const isEnd = n => n?.role === 'start' || n?.role === 'finish';
  function showToast(msg, isError = true) {
    clearTimeout(toastTimer);
    Object.assign(toast, { textContent: msg, hidden: false });
    toast.classList.toggle('error', isError);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 4200);
  }
  async function api(url, method = 'GET', body) {
    try {
      const res = await fetch(url, { method, cache: 'no-store', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body) });
      const payload = await res.json();
      if (payload.state) {
        state = payload.state;
        if (!getNode(selectedId) || isEnd(getNode(selectedId))) selectedId = null;
        renderAll();
      }
      if (res.ok) return payload;
      showToast(payload.error || 'The request could not be completed.');
    } catch { showToast('Could not reach the Flask server. Check the connection and retry.'); }
    return null;
  }
  function cardHTML(node, i) {
    const id = esc(node.id), role = node.role, label = esc(node.name);
    const level = role === 'start' ? 'LEVEL 0 · FIXED' : role === 'finish' ? 'LAST LEVEL · FIXED' : `LEVEL ${node.level ?? 1}`;
    const chips = node.edges.map(e => `<span class="connection-chip"><span>${esc(nameOf(e.to))}</span><strong>${esc(e.weight)}</strong>
      <button type="button" aria-label="Remove connection to ${esc(nameOf(e.to))}" title="Remove connection" data-action="remove-edge" data-node-id="${id}" data-target-id="${esc(e.to)}">×</button></span>`).join('');
    const options = state.nodes.filter(o => o.id !== node.id).map(o => `<option value="${esc(o.id)}">${esc(o.name.trim() || '— unnamed node —')}</option>`).join('');
    const remove = state.nodes.length > 2
      ? `<button type="button" class="icon-button" aria-label="Delete node ${label}" title="Delete node" data-action="delete-node" data-node-id="${id}">×</button>`
      : '<span aria-hidden="true" style="width:34px;height:34px"></span>';
    const roleSelect = role
      ? `<select id="role-${id}" disabled aria-label="Fixed node role"><option>${role === 'start' ? 'Start · fixed left' : 'Destination · fixed right'}</option></select>`
      : `<select id="role-${id}" data-action="update-role" data-node-id="${id}"><option value="">Regular</option><option value="start">Start</option><option value="finish">Destination</option></select>`;
    return `<article class="node-card${role ? ` is-${role}` : ''}" data-card-id="${id}">
      <div class="node-card-head"><div class="node-card-title"><span class="node-index">${String(i + 1).padStart(2, '0')}</span>
        <span class="node-name-heading">${esc(node.name.trim() || 'UNNAMED NODE')}</span></div><span class="node-level-badge">${level}</span>${remove}</div>
      <div class="field-row">
        <div class="field"><label for="name-${id}">Node name</label>
          <input id="name-${id}" type="text" maxlength="24" autocomplete="off" value="${label}" placeholder="e.g. A" data-action="update-name" data-node-id="${id}"></div>
        <div class="field"><label for="role-${id}">Role</label>${roleSelect}</div>
      </div>
      <div class="connections">
        <div class="connections-head"><span class="mini-label">Outgoing connections</span><span class="mini-label">${String(node.edges.length).padStart(2, '0')}</span></div>
        <div class="connection-list">${chips || '<span class="empty-edges">NO CONNECTIONS YET</span>'}</div>
      </div>
      <form class="edge-form" data-action="add-edge-form" data-node-id="${id}"><select name="to" aria-label="Destination node" required>${options}</select>
        <input name="weight" type="number" min="0" step="any" value="1" aria-label="Connection weight" required>
        <button type="submit" class="edge-add" aria-label="Add connection" title="Add connection">+</button></form></article>`;
  }
  function renderCards() {
    nodeCount.textContent = `${String(state.nodes.length).padStart(2, '0')} NODES`;
    nodeCards.innerHTML = state.nodes.map(cardHTML).join('') + `<div class="editor-actions"><button type="button" class="add-node-button"
      data-action="add-node" aria-label="Add node" title="Add node" ${busy === 'add' || state.nodes.length >= 40 ? 'disabled' : ''}>+</button></div>`;
    solveButton.disabled = busy === 'solve';
    solveLabel.textContent = busy === 'solve' ? 'SOLVING…' : 'SOLVE';
  }
  function renderGraph() {
    const nodes = state.nodes.filter(n => n.name.trim());
    const W = Math.max(panel.clientWidth - 10, 320), H = Math.max(panel.clientHeight - 10, 300);
    const maxLevel = Math.max(2, Number(state.max_level) || 2), compact = W < 600, pad = compact ? 62 : 110;
    const fitGap = (W - 2 * pad) / maxLevel, fits = fitGap >= (compact ? 82 : 168);
    const gap = fits ? fitGap : 230, vw = fits ? W : 2 * pad + maxLevel * gap;
    const maxW = Math.max(70, Math.min(210, gap * (compact ? 0.72 : 0.78)));
    const levels = Array.from({ length: maxLevel + 1 }, () => []);
    nodes.forEach(n => levels[n.role === 'start' ? 0 : n.role === 'finish' ? maxLevel : Math.min(maxLevel - 1, Math.max(1, Number(n.level) || 1))].push(n));
    const vh = Math.max(H, 180 + Math.max(1, ...levels.map(l => l.length)) * 120), top = 126, space = vh - top - 70;
    Object.assign(svg.style, { width: `${vw}px`, height: `${vh}px` });
    svg.setAttribute('viewBox', `0 0 ${vw} ${vh}`);
    const pos = new Map();
    levels.forEach((list, lv) => list.forEach((n, row) => pos.set(n.id, { n, lv, h: 68, x: pad + lv * gap, y: top + (row + 1) * space / (list.length + 1),
      w: Math.min(Math.max(88, Math.min(210, n.name.trim().length * 9 + 48)), maxW) })));
    const sol = state.solution, path = sol?.reachable && Array.isArray(sol.pathIds) ? sol.pathIds : [];
    const solEdges = new Set(path.slice(1).map((id, i) => `${path[i]}->${id}`));
    const guides = levels.map((_, lv) => {
      const x = pad + lv * gap, last = lv === maxLevel;
      const title = compact ? (lv === 0 ? 'START · 0' : last ? 'END · LAST' : `LEVEL ${lv}`) : (lv === 0 ? 'START · LEVEL 0' : last ? 'DESTINATION · LAST LEVEL' : `BFS LEVEL ${lv}`);
      return `<line class="level-divider" x1="${x}" y1="88" x2="${x}" y2="${vh - 40}" /><text class="level-header" x="${x}" y="76">${title}</text>`;
    }).join('');
    const edges = nodes.flatMap(src => src.edges.map(e => {
      const a = pos.get(src.id), b = pos.get(e.to);
      if (!a || !b) return '';
      const dx = b.x - a.x, dy = b.y - a.y, norm = Math.hypot(dx, dy) || 1, dir = src.id < b.n.id ? 1 : -1;
      const f = p => 1 / Math.max(Math.abs(dx) / (p.w / 2), Math.abs(dy) / (p.h / 2), 1e-4);
      const s = { x: a.x + dx * f(a), y: a.y + dy * f(a) }, t = { x: b.x - dx * f(b), y: b.y - dy * f(b) };
      // same-level links take a wide arc so they don't cut through other node boxes
      const curve = a.lv === b.lv ? 260 * dir : b.n.edges.some(i => i.to === src.id) ? 30 * dir : 0;
      const c = { x: (s.x + t.x) / 2 - dy / norm * curve, y: (s.y + t.y) / 2 + dx / norm * curve };
      const lx = (s.x + 2 * c.x + t.x) / 4, ly = (s.y + 2 * c.y + t.y) / 4;
      return `<g class="graph-edge"><path class="edge-path${solEdges.has(`${src.id}->${e.to}`) ? ' is-solution' : ''}" d="M ${s.x} ${s.y} Q ${c.x} ${c.y} ${t.x} ${t.y}" />
        <rect class="edge-label-bg" x="${lx - 21}" y="${ly - 13}" width="42" height="26" /><text class="edge-label" x="${lx}" y="${ly}">${esc(e.weight)}</text></g>`;
    })).filter(Boolean);
    const nodeMarkup = nodes.map(n => {
      const p = pos.get(n.id), nm = n.name.trim();
      const cls = ['graph-node', n.role || 'regular', path.includes(n.id) && 'solution', selectedId === n.id && 'selected'].filter(Boolean).join(' ');
      const maxChars = Math.max(3, Math.floor((p.w - 20) / (compact ? 7 : 8.5)));
      const info = n.role === 'start' ? 'start, fixed left' : n.role === 'finish' ? 'destination, fixed right' : `level ${p.lv}`;
      return `<g class="${cls}" transform="translate(${p.x}, ${p.y})" data-node-id="${esc(n.id)}" tabindex="0" role="button" aria-label="Select node ${esc(n.name)}${n.role ? ', fixed endpoint' : ', move between levels'}">
        <title>${esc(n.name)} — ${info}</title>
        <rect class="graph-node-rect" x="${-p.w / 2}" y="${-p.h / 2}" width="${p.w}" height="${p.h}" rx="0" />
        <text class="graph-node-text" x="0" y="${n.role ? -5 : -3}">${esc(nm.length > maxChars ? nm.slice(0, maxChars - 1) + '…' : nm)}</text>
        <text class="graph-node-role" x="0" y="18">${n.role === 'start' ? 'START' : n.role === 'finish' ? 'DESTINATION' : `LEVEL ${p.lv}`}</text></g>`;
    }).join('');
    const marker = (id, fill) => `<marker id="${id}" markerWidth="9" markerHeight="9" refX="7" refY="3.5" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,7 L7,3.5 z" fill="${fill}"></path></marker>`;
    svg.innerHTML = `<defs>${marker('arrow', '#92928b')}${marker('arrow-solution', '#e3342b')}</defs>${guides}${edges.join('')}${nodeMarkup}` +
      (nodes.length ? '' : `<text x="${vw / 2}" y="${vh / 2}" text-anchor="middle" fill="#77776f" font-family="ui-monospace,monospace" font-size="13">ADD A NAMED NODE TO BEGIN</text>`);
    svg.setAttribute('aria-label', `Preview graph with ${nodes.length} named nodes, ${edges.length} connections, start on the left and destination on the right`);
  }
  function renderLevelMovePanel() {
    const n = getNode(selectedId);
    if ((movePanel.hidden = !n || isEnd(n))) return;
    selectedNodeName.textContent = n.name.trim() || 'UNNAMED NODE';
    selectedNodeLevel.textContent = `BFS LEVEL ${n.level ?? 1}`;
    [leftBtn.disabled, rightBtn.disabled] = [busy === 'move' || Number(n.level) <= 1, busy === 'move'];
  }
  function renderSolution() {
    const sol = state.solution;
    if ((solutionCard.hidden = !sol)) return;
    solutionValue.textContent = sol.reachable ? `Total cost: ${sol.cost}` : 'No route found';
    if (sol.reachable) solutionPath.innerHTML = `<strong>SHORTEST PATH</strong><br>${sol.pathNames.map(esc).join(' → ')}`;
    else solutionPath.textContent = sol.message || 'No path connects the selected start and destination.';
  }
  function renderAll() { renderCards(); renderGraph(); renderLevelMovePanel(); renderSolution(); }
  nodeCards.addEventListener('change', e => {
    const { action, nodeId } = e.target.dataset;
    if (nodeId && (action === 'update-name' || action === 'update-role'))
      api(`/api/nodes/${enc(nodeId)}`, 'PATCH', action === 'update-name' ? { name: e.target.value } : { role: e.target.value });
  });
  nodeCards.addEventListener('submit', e => {
    const form = e.target.closest('form[data-action="add-edge-form"]');
    if (!form) return;
    e.preventDefault();
    const w = form.elements.weight.value;
    if (w === '' || !Number.isFinite(Number(w)) || Number(w) < 0) return showToast('Enter a finite weight greater than or equal to zero.');
    api(`/api/nodes/${enc(form.dataset.nodeId)}/edges`, 'POST', { to: form.elements.to.value, weight: Number(w) });
  });
  nodeCards.addEventListener('click', async e => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;
    const { action, nodeId, targetId } = btn.dataset;
    if (action === 'delete-node') { if (confirm(`Delete node “${nameOf(nodeId)}” and all its connections?`)) api(`/api/nodes/${enc(nodeId)}`, 'DELETE'); }
    else if (action === 'remove-edge') api(`/api/nodes/${enc(nodeId)}/edges/${enc(targetId)}`, 'DELETE');
    else if (action === 'add-node' && !busy) {
      busy = 'add'; renderCards();
      const before = state.nodes.length, payload = await api('/api/nodes', 'POST', {});
      busy = ''; renderCards();
      if (!payload) return;
      const newest = state.nodes[state.nodes.length - 1];
      nodeCards.scrollTo({ left: nodeCards.scrollWidth, behavior: 'smooth' });
      setTimeout(() => document.getElementById(`name-${newest.id}`)?.focus(), 160);
      if (state.nodes.length > before) showToast(`Node ${newest.name} added.`, false);
    }
  });
  solveButton.addEventListener('click', async () => {
    if (busy) return;
    busy = 'solve'; renderCards(); const payload = await api('/api/solve', 'POST', {});
    busy = ''; renderCards(); renderSolution(); const sol = payload?.state?.solution;
    if (sol) showToast(sol.reachable ? 'Shortest path calculated.' : sol.message, !sol.reachable);
  });
  function selectNode(el) {
    const n = getNode(el?.dataset?.nodeId);
    if (!n) return;
    selectedId = isEnd(n) ? null : n.id;
    renderGraph(); renderLevelMovePanel();
    if (isEnd(n)) showToast(n.role === 'start' ? 'The start node is locked to level 0 on the far left.' : 'The destination is locked to the last level on the far right.', false);
  }
  svg.addEventListener('click', e => selectNode(e.target.closest('.graph-node[data-node-id]')));
  svg.addEventListener('keydown', e => {
    const el = e.target.closest('.graph-node[data-node-id]');
    if (el && ['Enter', ' '].includes(e.key)) { e.preventDefault(); selectNode(el); }
  });
  async function moveSelected(direction) {
    const id = selectedId;
    if (!id || busy === 'move') return;
    busy = 'move'; renderLevelMovePanel();
    await api(`/api/nodes/${enc(id)}/level`, 'POST', { direction });
    busy = ''; renderGraph(); renderLevelMovePanel();
  }
  [[leftBtn, 'left'], [rightBtn, 'right']].forEach(([btn, dir]) => btn.addEventListener('click', () => moveSelected(dir)));
  // Re-render only when the panel's own size changes, never in reaction to scrollbars.
  let lastW = 0, lastH = 0;
  const onResize = () => {
    if (panel.clientWidth === lastW && panel.clientHeight === lastH) return;
    [lastW, lastH] = [panel.clientWidth, panel.clientHeight];
    renderGraph();
  };
  if ('ResizeObserver' in window) new ResizeObserver(onResize).observe(panel); else window.addEventListener('resize', onResize);
  api('/api/state');
})();
