/* Homelab Inventory — Alpine.js front-end.
 * Talks to FastAPI /api/* endpoints. Inside HA Ingress, requests are
 * relative to the ingress URL so everything Just Works.
 */

const SECTION_FIELDS = {
  hardware: [
    { key: 'id',          label: 'ID',          table: true },
    { key: 'name',        label: 'Name',        table: true },
    { key: 'type',        label: 'Type',        table: true, type: 'select',
      options: ['server','nas','iot','network','av','compute','sensor','hub','other'] },
    { key: 'location',    label: 'Location',    table: true },
    { key: 'vendor',      label: 'Vendor' },
    { key: 'model',       label: 'Model' },
    { key: 'specs',       label: 'Specs',       type: 'textarea' },
    { key: 'role',        label: 'Role',        table: true },
    { key: 'ip',          label: 'IP' },
    { key: 'mac',         label: 'MAC' },
    { key: 'purchased',   label: 'Purchased' },
    { key: 'ha_entity_id',label: 'HA entity ID (for uptime)' },
    { key: 'ha_device_id',label: 'HA device ID (optional link)' },
    { key: 'notes',       label: 'Notes',       type: 'textarea' },
    { key: 'tags',        label: 'Tags',        type: 'tags' },
  ],
  applications: [
    { key: 'id',          label: 'ID',          table: true },
    { key: 'name',        label: 'Name',        table: true },
    { key: 'type',        label: 'Type',        table: true, type: 'select',
      options: ['ha_addon','container','native','vm','saas','other'] },
    { key: 'runs_on',     label: 'Runs on (hardware id)', table: true },
    { key: 'url',         label: 'URL' },
    { key: 'version',     label: 'Version' },
    { key: 'purpose',     label: 'Purpose',     table: true },
    { key: 'ha_entity_id',label: 'HA entity ID (for uptime)' },
    { key: 'notes',       label: 'Notes',       type: 'textarea' },
    { key: 'tags',        label: 'Tags',        type: 'tags' },
  ],
  integrations: [
    { key: 'id',       label: 'ID',       table: true },
    { key: 'name',     label: 'Name',     table: true },
    { key: 'type',     label: 'Type',     table: true, type: 'select',
      options: ['ha_integration','cloud','api','service','other'] },
    { key: 'account',  label: 'Account',  table: true },
    { key: 'purpose',  label: 'Purpose',  table: true },
    { key: 'notes',    label: 'Notes',    type: 'textarea' },
    { key: 'tags',     label: 'Tags',     type: 'tags' },
  ],
  'network/subnets': [
    { key: 'id',       label: 'ID',       table: true },
    { key: 'name',     label: 'Name',     table: true },
    { key: 'cidr',     label: 'CIDR',     table: true },
    { key: 'vlan_id',  label: 'VLAN',     table: true, type: 'number' },
    { key: 'gateway',  label: 'Gateway',  table: true },
    { key: 'purpose',  label: 'Purpose' },
    { key: 'notes',    label: 'Notes',    type: 'textarea' },
  ],
  'network/vlans': [
    { key: 'id',       label: 'ID',       table: true },
    { key: 'name',     label: 'Name',     table: true },
    { key: 'vlan_id',  label: 'VLAN ID',  table: true, type: 'number' },
    { key: 'purpose',  label: 'Purpose',  table: true },
    { key: 'notes',    label: 'Notes',    type: 'textarea' },
  ],
  'network/hosts': [
    { key: 'id',          label: 'ID',          table: true },
    { key: 'hostname',    label: 'Hostname',    table: true },
    { key: 'ip',          label: 'IP',          table: true },
    { key: 'hardware_id', label: 'Hardware',    table: true },
    { key: 'subnet_id',   label: 'Subnet',      table: true },
    { key: 'purpose',     label: 'Purpose' },
    { key: 'notes',       label: 'Notes',       type: 'textarea' },
  ],
};

function tableCols(sectionKey) {
  return SECTION_FIELDS[sectionKey].filter(f => f.table);
}

const API = './api';

function fmtDuration(seconds) {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return '—';
  const s = Math.max(0, Math.floor(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${sec}s`;
  return `${sec}s`;
}

function app() {
  return {
    tab: 'overview',
    inv: { hardware: [], applications: [], integrations: [], network: { subnets: [], vlans: [], hosts: [] } },
    rawYaml: '',
    rawError: '',
    saving: false,
    lastSaved: '',
    editing: null,
    editingSection: '',
    editingIsNew: false,
    editingFields: [],
    editError: '',
    graphNetwork: null,
    uptime: {},
    ha: { configured: null },
    haDevices: [],
    haFilter: '',
    _uptimePollHandle: null,

    tabs: [
      { id: 'overview',     label: 'Overview' },
      { id: 'hardware',     label: 'Hardware' },
      { id: 'applications', label: 'Applications' },
      { id: 'network',      label: 'Network' },
      { id: 'integrations', label: 'Integrations' },
      { id: 'topology',     label: 'Topology' },
      { id: 'ha',           label: 'HA Devices' },
      { id: 'yaml',         label: 'YAML' },
    ],

    integrationCols: tableCols('integrations'),

    networkSections: [
      { key: 'subnets', label: 'Subnets', cols: tableCols('network/subnets') },
      { key: 'vlans',   label: 'VLANs',   cols: tableCols('network/vlans') },
      { key: 'hosts',   label: 'Hosts',   cols: tableCols('network/hosts') },
    ],

    async init() {
      await this.reload();
      await this.loadHaStatus();
      this._uptimePollHandle = setInterval(() => this.loadUptime(), 15000);
      this.$watch('tab', t => {
        if (t === 'topology') this.$nextTick(() => this.renderGraph());
        if (t === 'ha' && !this.haDevices.length) this.loadHaDevices();
      });
      this.$watch('inv', () => { if (this.tab === 'topology') this.renderGraph(); }, { deep: true });
    },

    async reload() {
      try {
        const res = await fetch(`${API}/inventory`);
        this.inv = await res.json();
        const rawRes = await fetch(`${API}/inventory/raw`);
        this.rawYaml = await rawRes.text();
        await this.loadUptime();
        if (this.tab === 'topology') this.$nextTick(() => this.renderGraph());
      } catch (e) {
        console.error(e);
      }
    },

    async loadHaStatus() {
      try {
        const r = await fetch(`${API}/ha/status`);
        this.ha = await r.json();
      } catch { this.ha = { configured: false }; }
    },

    async loadHaDevices() {
      try {
        const r = await fetch(`${API}/ha/devices`);
        const j = await r.json();
        this.haDevices = j.devices || [];
      } catch { this.haDevices = []; }
    },

    filteredHaDevices() {
      const q = (this.haFilter || '').toLowerCase().trim();
      if (!q) return this.haDevices;
      return this.haDevices.filter(d =>
        (d.name || '').toLowerCase().includes(q) ||
        (d.manufacturer || '').toLowerCase().includes(q) ||
        (d.model || '').toLowerCase().includes(q) ||
        (d.entities || []).some(e => (e.entity_id || '').toLowerCase().includes(q))
      );
    },

    async loadUptime() {
      try {
        const r = await fetch(`${API}/uptime`);
        this.uptime = await r.json();
      } catch {}
    },

    trackedCount(state) {
      return Object.values(this.uptime).filter(u => u.current_state === state).length;
    },

    statusPill(entityId) {
      if (!entityId) return '';
      const u = this.uptime[entityId];
      if (!u) return '<span class="status-pill status-unknown">unknown</span>';
      const cls = u.current_state === 'up' ? 'status-up' : 'status-down';
      return `<span class="status-pill ${cls}">${u.current_state}</span>`;
    },

    streakOf(entityId) {
      if (!entityId) return '—';
      const u = this.uptime[entityId];
      if (!u) return '—';
      const dir = u.current_state === 'up' ? 'up' : 'down';
      return `${dir} ${fmtDuration(u.current_streak_seconds)}`;
    },

    uptimePctOf(entityId) {
      if (!entityId) return '—';
      const u = this.uptime[entityId];
      if (!u || u.uptime_pct === null || u.uptime_pct === undefined) return '—';
      return `${u.uptime_pct.toFixed(1)}%`;
    },

    appsByHardware() {
      const hwById = Object.fromEntries((this.inv.hardware || []).map(h => [h.id, h]));
      const groups = new Map();
      (this.inv.applications || []).forEach(a => {
        const key = a.runs_on || '';
        if (!groups.has(key)) {
          const hw = hwById[a.runs_on];
          groups.set(key, {
            hardware_id: a.runs_on || null,
            hardware_name: hw ? hw.name : (a.runs_on ? `(unknown: ${a.runs_on})` : 'Unassigned'),
            hardware_type: hw ? hw.type : null,
            apps: [],
          });
        }
        groups.get(key).apps.push(a);
      });
      // Also include hardware rows that have zero apps but exist — easier to spot empty hosts.
      (this.inv.hardware || []).forEach(h => {
        if (!groups.has(h.id)) {
          groups.set(h.id, {
            hardware_id: h.id, hardware_name: h.name, hardware_type: h.type, apps: [],
          });
        }
      });
      // Sort: real hardware first (by name), Unassigned last.
      return Array.from(groups.values()).sort((a, b) => {
        if (!a.hardware_id && b.hardware_id) return 1;
        if (a.hardware_id && !b.hardware_id) return -1;
        return (a.hardware_name || '').localeCompare(b.hardware_name || '');
      }).filter(g => g.apps.length > 0 || g.hardware_id);
    },

    renderCell(item, col) {
      const v = item[col.key];
      if (Array.isArray(v)) return v.join(', ');
      if (v === null || v === undefined || v === '') return '—';
      return v;
    },

    openNew(sectionKey) {
      this.editingSection = sectionKey;
      this.editingIsNew = true;
      this.editingFields = SECTION_FIELDS[sectionKey];
      const blank = {};
      this.editingFields.forEach(f => {
        if (f.type === 'tags') blank[f.key] = [];
        else if (f.type === 'select') blank[f.key] = f.options[f.options.length - 1];
        else if (f.type === 'number') blank[f.key] = null;
        else blank[f.key] = '';
      });
      this.editing = blank;
      this.editError = '';
    },

    openEdit(sectionKey, item) {
      this.editingSection = sectionKey;
      this.editingIsNew = false;
      this.editingFields = SECTION_FIELDS[sectionKey];
      this.editing = JSON.parse(JSON.stringify(item));
      this.editError = '';
    },

    async saveItem() {
      this.saving = true;
      this.editError = '';
      try {
        const body = { ...this.editing };
        Object.keys(body).forEach(k => {
          if (body[k] === '' || body[k] === null) delete body[k];
        });
        const url = this.editingIsNew
          ? `${API}/${this.editingSection}`
          : `${API}/${this.editingSection}/${encodeURIComponent(this.editing.id)}`;
        const method = this.editingIsNew ? 'POST' : 'PUT';
        const res = await fetch(url, {
          method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          this.editError = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
          return;
        }
        this.editing = null;
        await this.reload();
        this.markSaved();
      } finally {
        this.saving = false;
      }
    },

    async del(sectionKey, id) {
      if (!confirm(`Delete ${id}?`)) return;
      this.saving = true;
      try {
        await fetch(`${API}/${sectionKey}/${encodeURIComponent(id)}`, { method: 'DELETE' });
        await this.reload();
        this.markSaved();
      } finally {
        this.saving = false;
      }
    },

    async saveRaw() {
      this.saving = true;
      this.rawError = '';
      try {
        const res = await fetch(`${API}/inventory/raw`, {
          method: 'PUT',
          headers: { 'Content-Type': 'text/plain' },
          body: this.rawYaml,
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          this.rawError = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
          return;
        }
        await this.reload();
        this.markSaved();
      } finally {
        this.saving = false;
      }
    },

    markSaved() {
      const d = new Date();
      this.lastSaved = d.toLocaleTimeString();
    },

    renderGraph() {
      const container = document.getElementById('graph');
      if (!container) return;

      const dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      const nodes = [];
      const edges = [];
      const palette = {
        server: '#10b981', nas: '#0ea5e9', iot: '#f59e0b', network: '#6366f1',
        av: '#ef4444', compute: '#22d3ee', sensor: '#84cc16', hub: '#a855f7', other: '#64748b',
      };

      (this.inv.hardware || []).forEach(h => {
        nodes.push({
          id: 'hw:' + h.id,
          label: h.name,
          title: [h.type, h.role, h.location].filter(Boolean).join(' • '),
          shape: 'box',
          color: { background: palette[h.type] || palette.other, border: dark ? '#e2e8f0' : '#0f172a' },
          font: { color: 'white' },
        });
      });

      (this.inv.applications || []).forEach(a => {
        nodes.push({
          id: 'app:' + a.id,
          label: a.name,
          title: [a.type, a.purpose].filter(Boolean).join(' • '),
          shape: 'ellipse',
          color: {
            background: dark ? '#312e81' : '#ede9fe',
            border:     dark ? '#a78bfa' : '#7c3aed',
          },
          font: { color: dark ? '#e2e8f0' : '#1e1b4b' },
        });
        if (a.runs_on) {
          edges.push({ from: 'app:' + a.id, to: 'hw:' + a.runs_on, dashes: true });
        }
      });

      (this.inv.integrations || []).forEach(i => {
        nodes.push({
          id: 'int:' + i.id,
          label: i.name,
          title: [i.type, i.purpose].filter(Boolean).join(' • '),
          shape: 'diamond',
          color: {
            background: dark ? '#422006' : '#fef3c7',
            border:     dark ? '#fbbf24' : '#d97706',
          },
          font: { color: dark ? '#fde68a' : '#78350f' },
        });
      });

      const data = {
        nodes: new vis.DataSet(nodes),
        edges: new vis.DataSet(edges),
      };
      const options = {
        physics: { stabilization: { iterations: 80 } },
        interaction: { hover: true, tooltipDelay: 150 },
        nodes: { borderWidth: 1, margin: 8 },
        edges: { color: { color: dark ? '#475569' : '#94a3b8' }, smooth: { type: 'continuous' } },
      };

      if (this.graphNetwork) this.graphNetwork.destroy();
      this.graphNetwork = new vis.Network(container, data, options);
    },
  };
}

window.app = app;
