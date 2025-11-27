// ---------- helpers ----------
function linkToEncode(item) {
    const id = item.id || "";
    const url = id.startsWith("http") ? id : ("https://www.encodeproject.org" + id);
    const label = item.accession || "View";
    return '<a href="' + url + '" target="_blank" rel="noopener">' + label + '</a>';
}

function setLoading(isLoading) {
    const btn = document.getElementById('searchBtn');
    const loading = document.getElementById('loading');
    const form = document.getElementById('searchForm');
    if (isLoading) {
        loading.style.display = '';
        btn.disabled = true;
        btn.dataset.prev = btn.textContent;
        btn.textContent = 'Searching…';
        Array.from(form.elements).forEach(el => el.disabled = true);
    } else {
        loading.style.display = 'none';
        btn.disabled = false;
        btn.textContent = btn.dataset.prev || 'Search';
        Array.from(form.elements).forEach(el => el.disabled = false);
    }
}

// click-outside helper for floating panels
function setupClickOutside(panelEl, toggleBtn) {
    document.addEventListener('click', (ev) => {
        const isToggle = toggleBtn.contains(ev.target);
        const isInside = panelEl.contains(ev.target);
        if (!isToggle && !isInside) {
            panelEl.style.display = 'none';
        }
    });
}

// ---------- globals ----------
let OPTIONS = null;

// ----- Cell tree state -----
let CELL_TREE = null;
let NODE_STATE = {};           // id -> 1 included, 2 excluded
let MARKER_BY_ID = {};         // id -> [elements]
let NODE_BY_ID = {};
let CHILDREN_BY_ID = {};
let LEAVES_BY_ID = {};

function stateOf(id) {
    return NODE_STATE[id] || 2;
}             // <<< FIX: define stateOf
function registerMarker(id, el) {                                 // <<< FIX: define registerMarker
    if (!MARKER_BY_ID[id]) MARKER_BY_ID[id] = [];
    MARKER_BY_ID[id].push(el);
}

function normalizeLeafName(m) {
    if (typeof m === 'string') return m;
    return m.label || m.title || String(m);
}

function indexTreeForFastOps() {
    NODE_BY_ID = {};
    CHILDREN_BY_ID = {};
    LEAVES_BY_ID = {};
    (function collect(n) {
        NODE_BY_ID[n.id] = n;
        (n.children || []).forEach(collect);
    })(CELL_TREE);
    for (const id in NODE_BY_ID) {
        const n = NODE_BY_ID[id];
        CHILDREN_BY_ID[id] = (n.children || []).map(c => c.id);
    }

    function computeLeaves(id) {
        const n = NODE_BY_ID[id];
        const out = new Set();
        (n.members || []).forEach(m => out.add(normalizeLeafName(m)));
        for (const cid of (CHILDREN_BY_ID[id] || [])) computeLeaves(cid).forEach(x => out.add(x));
        return Array.from(out);
    }

    for (const id in NODE_BY_ID) LEAVES_BY_ID[id] = computeLeaves(id);
}

// ---------- cell UI (native checkboxes to match table first column) ----------
function renderCellTree(filterText = '') {
    MARKER_BY_ID = {};
    const container = document.getElementById('cellTree');
    container.innerHTML = '';
    if (!CELL_TREE) return;

    const ft = (filterText || '').trim().toLowerCase();

    function nodeMatches(node) {
        if (!ft) return true;
        const label = (node.label || '').toLowerCase();
        if (label.includes(ft)) return true;
        const leaves = LEAVES_BY_ID[node.id] || [];
        return leaves.some(x => String(x).toLowerCase().includes(ft));
    }

    function renderNode(node, depth, into) {
        if (!nodeMatches(node)) return;

        const nid = node.id;
        const st = stateOf(nid);
        const hasChildren = (node.children && node.children.length);
        const hasMembers = (node.members && node.members.length);

        const row = document.createElement('div');
        row.className = 'tree-row';
        row.style.marginLeft = (depth * 14) + 'px';

        const caret = document.createElement('span');
        caret.className = 'caret';
        const willShowChildren = (hasChildren || hasMembers);
        caret.textContent = willShowChildren ? (ft ? '▾' : '▸') : '';
        caret.dataset.open = ft ? '1' : '0';

        const toggle = document.createElement('input');
        toggle.type = 'checkbox';
        toggle.dataset.id = nid;
        toggle.checked = (st === 1);
        registerMarker(nid, toggle);

        const label = document.createElement('span');
        const memCount = (LEAVES_BY_ID[nid] || []).length;
        label.textContent = node.label + (memCount ? ` (${memCount})` : '');
        label.className = 'label';

        row.appendChild(caret);
        row.appendChild(toggle);
        row.appendChild(label);
        into.appendChild(row);

        let wrap = null;
        if (willShowChildren) {
            wrap = document.createElement('div');
            wrap.style.display = ft ? '' : 'none';
            into.appendChild(wrap);
        }

        // Toggle node (instant visual update)
        toggle.addEventListener('change', (ev) => {
            ev.stopPropagation();
            const next = toggle.checked ? 1 : 2;
            NODE_STATE[nid] = next;                // set this node
            setNodeStateCascadeDeep(nid, next);    // cascade + refresh all
        });

        if (willShowChildren) {
            caret.style.cursor = 'pointer';
            caret.addEventListener('click', () => {
                const open = caret.dataset.open === '1';
                caret.dataset.open = open ? '0' : '1';
                caret.textContent = open ? '▸' : '▾';
                wrap.style.display = open ? 'none' : '';
            });
            (node.children || []).forEach(ch => renderNode(ch, depth + 1, wrap));
            (node.members || []).map(normalizeLeafName).filter(name => !ft || String(name).toLowerCase().includes(ft)).forEach(name => {
                const lid = 'leaf::' + name;
                const lst = stateOf(lid);
                const leaf = document.createElement('div');
                leaf.className = 'tree-row';
                leaf.style.marginLeft = ((depth + 1) * 14) + 'px';
                const spacer = document.createElement('span');
                spacer.className = 'caret';
                spacer.textContent = '';
                const leafToggle = document.createElement('input');
                leafToggle.type = 'checkbox';
                leafToggle.dataset.id = lid;
                leafToggle.checked = (lst === 1);
                registerMarker(lid, leafToggle);
                const leafLabel = document.createElement('span');
                leafLabel.className = 'label';
                leafLabel.textContent = name;
                leaf.appendChild(spacer);
                leaf.appendChild(leafToggle);
                leaf.appendChild(leafLabel);
                wrap.appendChild(leaf);

                leafToggle.addEventListener('change', (ev) => {
                    ev.stopPropagation();
                    const next = leafToggle.checked ? 1 : 2;
                    NODE_STATE[lid] = next;
                    setNodeStateCascadeDeep(lid, next);
                });
            });
        }
    }

    renderNode(CELL_TREE, 0, container);
}

function collectDescNodeIds(rootId) {
    const out = new Set();
    (function walk(id) {
        for (const cid of (CHILDREN_BY_ID[id] || [])) {
            out.add(cid);
            walk(cid);
        }
    })(rootId);
    return Array.from(out);
}

function deepLeafNamesFrom(id) {
    return (LEAVES_BY_ID[id] || []).map(normalizeLeafName);
}

function refreshSingleMarker(id) {
    const arr = MARKER_BY_ID[id];
    if (!arr) return;
    const checked = (stateOf(id) === 1);
    for (const b of arr) b.checked = checked;
}

function refreshAllMarkers() {
    for (const id of Object.keys(MARKER_BY_ID)) refreshSingleMarker(id);
}

function setNodeStateCascadeDeep(nid, state) {
    NODE_STATE[nid] = state;
    refreshSingleMarker(nid);
    // cascade to leaves
    (LEAVES_BY_ID[nid] || []).forEach(name => {
        const lid = 'leaf::' + name;
        NODE_STATE[lid] = state;
        refreshSingleMarker(lid);
    });
    // cascade to descendants
    collectDescNodeIds(nid).forEach(cid => {
        NODE_STATE[cid] = state;
        refreshSingleMarker(cid);
        (LEAVES_BY_ID[cid] || []).forEach(name => {
            const lid = 'leaf::' + name;
            NODE_STATE[lid] = state;
            refreshSingleMarker(lid);
        });
    });
    // update hidden field + summary
    updateCellIncludesHidden();
    updateCellSummary();
}

function updateCellIncludesHidden() {
    const names = Object.keys(NODE_STATE).filter(id => id.startsWith('leaf::') && NODE_STATE[id] === 1).map(id => id.slice('leaf::'.length));
    document.getElementById('cell_includes_json').value = JSON.stringify(names);
}

function updateCellSummary() {
    const val = document.getElementById('cell_includes_json').value || '[]';
    let arr = [];
    try {
        arr = JSON.parse(val);
    } catch (_) {
    }
    const sumEl = document.getElementById('cellSummary');
    sumEl.textContent = arr.length ? (`${arr.length} cell types selected`) : 'No cell types selected';
}

// ---------- targets (single-select list) ----------
let ALL_TARGETS = [];
let SELECTED_TARGET = '';
let T_MARKER_BY_ID = {};

function tRegisterMarker(id, el) {
    if (!T_MARKER_BY_ID[id]) T_MARKER_BY_ID[id] = [];
    T_MARKER_BY_ID[id].push(el);
}

function renderTargetList(filterText = '') {
    const list = document.getElementById('targetTree');
    list.innerHTML = '';
    const ft = (filterText || '').trim().toLowerCase();
    const filtered = ALL_TARGETS.filter(t => t.toLowerCase().includes(ft));

    filtered.forEach(t => {
        const row = document.createElement('div');
        row.className = 'tree-row';
        const caret = document.createElement('span');
        caret.className = 'caret';
        caret.textContent = '';
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'marker';
        toggle.textContent = (SELECTED_TARGET === t ? '✓' : ' ');
        tRegisterMarker('leaf::' + t, toggle);
        const label = document.createElement('span');
        label.className = 'label';
        label.textContent = t;

        row.appendChild(caret);
        row.appendChild(toggle);
        row.appendChild(label);
        list.appendChild(row);

        toggle.addEventListener('click', () => {
            SELECTED_TARGET = (SELECTED_TARGET === t) ? '' : t;
            document.getElementById('target').value = SELECTED_TARGET || '';
            renderTargetList(ft);
            updateTargetSummary();
        });
    });
}

function updateTargetSummary() {
    const val = document.getElementById('target').value || '';
    const sumEl = document.getElementById('targetSummary');
    sumEl.textContent = val ? ('Target: ' + val) : 'No target selected';
}

// ---------- results ----------
let LAST_DATA = null;
let DISPLAY_COUNT = 0;

// ---------- options / boot ----------
async function populateOptions() {
    try {
        const r = await fetch('/options', {cache: 'no-store'});
        const data = await r.json();
        if (!data.ok) throw new Error(data.error || 'Failed loading options');

        // Fill assay from response if present — show only first two options
        const assays = data.assays || [];
        const assaySel = document.getElementById('assay');
        if (assays.length) {
            const topAssays = assays.slice(0, 2);
            assaySel.innerHTML =
                '<option value="">Assay</option>' +
                topAssays.map(a => `<option>${a}</option>`).join('');
            if (!assaySel.value) {
                assaySel.value = topAssays.includes('Histone ChIP-seq') ? 'Histone ChIP-seq' : topAssays[0];
            }
        }

        // Targets data (flat)
        ALL_TARGETS = data.targets || [];
        renderTargetList('');
        updateTargetSummary();

        // Cell tree
        CELL_TREE = data.cell_tree || null;
        NODE_STATE = {};
        if (CELL_TREE) {
            indexTreeForFastOps();
            // default: everything excluded
            (function seed(n) {
                NODE_STATE[n.id] = 2;
                (n.children || []).forEach(seed);
                (n.members || []).forEach(m => {
                    NODE_STATE['leaf::' + normalizeLeafName(m)] = 2;
                });
            })(CELL_TREE);
            renderCellTree('');
            updateCellIncludesHidden();
        }

        // Assemblies (no organism parameter) — show only first two options
        const ar = await fetch('/assemblies');
        const aj = await ar.json();
        const assemblySel = document.getElementById('assembly');
        const topAssemblies = (aj.assemblies || []).slice(0, 2);
        assemblySel.innerHTML = '<option value="">Assembly</option>' + topAssemblies.map(a => `<option>${a}</option>`).join('');

        // hide loader
        const el = document.getElementById('optionsLoading');
        if (el) el.style.display = 'none';

        // filters
        document.getElementById('targetFilter').addEventListener('input', (e) => renderTargetList(e.target.value));
        document.getElementById('cellFilter').addEventListener('input', (e) => renderCellTree(e.target.value));

        // submit
        document.getElementById('searchForm').addEventListener('submit', (e) => {
            e.preventDefault();
            run(false);
        });

    } catch (e) {
        const el = document.getElementById('optionsLoading');
        if (el) el.textContent = 'Error loading options: ' + e;
    }
}

// ---------- URLs modal ----------
const urlsModal = document.getElementById('urlsModal');
const urlsList = document.getElementById('urlsList');
const closeUrls = document.getElementById('closeUrls');
const showUrlsBtn = document.getElementById('showUrlsBtn');
showUrlsBtn.addEventListener('click', () => {
    urlsList.innerHTML = '';
    const data = LAST_DATA || {};
    if (data.urls && data.urls.length > 0) {
        data.urls.forEach((u, i) => {
            const li = document.createElement('li');
            li.innerHTML = `<a href="${u}" target="_blank" rel="noopener">Request ${i + 1}</a>`;
            urlsList.appendChild(li);
        });
    } else if (data.url) {
        const li = document.createElement('li');
        li.innerHTML = `<a href="${data.url}" target="_blank" rel="noopener">${data.url}</a>`;
        urlsList.appendChild(li);
    }
    urlsModal.style.display = '';
});
closeUrls.addEventListener('click', () => {
    urlsModal.style.display = 'none';
});

// ---------- table selection ----------
const processBtn = document.getElementById('processBtn');
const selectAllHeader = document.getElementById('selectAllHeader');

function updateSelectAllHeader() {
    const boxes = Array.from(document.querySelectorAll('#tbody .row-select'));
    if (boxes.length === 0) {
        selectAllHeader.checked = false;
        return;
    }
    selectAllHeader.checked = boxes.every(b => b.checked);
}

if (selectAllHeader) {
    selectAllHeader.addEventListener('change', () => {
        const boxes = document.querySelectorAll('#tbody .row-select');
        boxes.forEach(b => {
            b.checked = selectAllHeader.checked;
        });
    });
}

processBtn.addEventListener('click', async () => {
    try {
        const tbody = document.getElementById('tbody');
        const boxes = Array.from(tbody.querySelectorAll('.row-select'));
        const ids = [];
        boxes.forEach((b, idx) => {
            if (b.checked && LAST_DATA && Array.isArray(LAST_DATA.items) && LAST_DATA.items[idx]) {
                const it = LAST_DATA.items[idx];
                ids.push(it.id || it.accession); // prefer @id, fallback to accession
            }
        });
        if (ids.length === 0) {
            alert('Please select at least one file row.');
            return;
        }

        // NEW: save TSV on the server (app/ folder) instead of downloading to browser
        const r = await fetch('/batch-tsv-save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ids})
        });

        let data = null;
        try {
            data = await r.json();
        } catch (_) {
        }

            document.getElementById('meta').textContent = '';
            document.getElementById('actions').style.display = 'none';
            document.getElementById('table').style.display = 'none';
        if (!r.ok || !data || !data.ok) {
            const msg = (data && data.error) ? data.error : `HTTP ${r.status}`;
            alert('Failed to save TSV: ' + msg);
        } else {
            alert(`Updated TSV table:\n${data.saved_path}\nPlease update the Giggle Index`);
        }
    } catch (err) {
        console.error(err);
        document.getElementById('meta').textContent = '' + err;
        document.getElementById('actions').style.display = 'none';
        document.getElementById('table').style.display = 'none';
        alert('Error while processing selection: ' + err);
    }
});

// ---------- search ----------
async function run(append = false) {
    setLoading(true);
    updateCellSummary();
    updateTargetSummary();

    const p = new URLSearchParams();
    const assay = document.getElementById('assay').value;
    const assembly = document.getElementById('assembly').value;
    const limitVal = document.getElementById('limit').value;
    const cellIncJson = document.getElementById('cell_includes_json').value;
    const targIncJson = document.getElementById('target').value;

    p.append('type', 'File');
    if (assay) p.append('assay', assay);
    if (assembly) p.append('assembly', assembly);
    if (limitVal) p.append('limit', limitVal);
    p.append('sort', '-date_created');
    if (cellIncJson) p.append('cell_includes', cellIncJson);
    if (targIncJson) p.append('target', targIncJson);

    try {
        const r = await fetch('/search?' + p.toString(), {cache: 'no-store'});
        const data = await r.json();
        LAST_DATA = data;

        const meta = document.getElementById('meta');
        const table = document.getElementById('table');
        const tbody = document.getElementById('tbody');
        const actions = document.getElementById('actions');

        if (!data.ok) {
            meta.textContent = 'Error: ' + (data.error || 'unknown');
            table.style.display = 'none';
            actions.style.display = 'none';
            DISPLAY_COUNT = 0;
            setLoading(false);
            return;
        }

        let urlHtml = '—';
        if (data.urls && data.urls.length > 1) urlHtml = `Multiple (${data.urls.length})`;
        else if (data.url) urlHtml = `<a href="${data.url}" target="_blank" rel="noopener">${data.url}</a>`;
        meta.innerHTML = 'URL: ' + urlHtml + ' • Combined rows: ' + (data.returned ?? 0);

        if (!data.items || data.items.length === 0) {
            table.style.display = 'none';
            actions.style.display = 'none';
            DISPLAY_COUNT = 0;
            updateSelectAllHeader();
            setLoading(false);
            return;
        }

        table.style.display = '';
        actions.style.display = '';

        let startIndex = 0;
        if (!append) {
            tbody.innerHTML = '';
            DISPLAY_COUNT = 0;
        } else {
            startIndex = DISPLAY_COUNT;
        }
        const newItems = data.items.slice(startIndex);
        for (const it of newItems) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td><input type="checkbox" class="row-select"></td>'
                + '<td>' + linkToEncode(it) + '</td>'
                + '<td>' + (it.assembly || '—') + '</td>'
                + '<td>' + (it.cell_type || '—') + '</td>'
                + '<td>' + (it.target || '—') + '</td>';
            tbody.appendChild(tr);
            // keep header select-all in sync
            const cb = tr.querySelector('.row-select');
            cb.addEventListener('change', updateSelectAllHeader);
        }
        DISPLAY_COUNT = data.items.length;
        updateSelectAllHeader();
    } catch (e) {
        document.getElementById('meta').textContent = 'Error: ' + e;
        document.getElementById('actions').style.display = 'none';
        document.getElementById('table').style.display = 'none';
        DISPLAY_COUNT = 0;
    }
    setLoading(false);
}

// ---- panel toggles, filters, click-outside ----
const targetsPanel = document.getElementById('targetsPanel');
const toggleTargets = document.getElementById('toggleTargets');
toggleTargets.addEventListener('click', (e) => {
    e.preventDefault();
    targetsPanel.style.display = (targetsPanel.style.display === 'none' || !targetsPanel.style.display) ? '' : 'none';
});
setupClickOutside(targetsPanel, toggleTargets);

const cellsPanel = document.getElementById('cellsPanel');
const toggleCells = document.getElementById('toggleCells');
toggleCells.addEventListener('click', (e) => {
    e.preventDefault();
    cellsPanel.style.display = (cellsPanel.style.display === 'none' || !cellsPanel.style.display) ? '' : 'none';
});
setupClickOutside(cellsPanel, toggleCells);

// boot
window.addEventListener('DOMContentLoaded', async () => {
    const el = document.getElementById('optionsLoading');
    if (el) el.style.display = '';
    await populateOptions();
});

// Clear target
document.getElementById('clearTargets').addEventListener('click', function () {
    SELECTED_TARGET = '';
    document.getElementById('target').value = '';
    document.getElementById('targetFilter').value = '';
    renderTargetList('');
    updateTargetSummary();
});
