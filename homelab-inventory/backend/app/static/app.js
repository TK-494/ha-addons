/* Homelab Inventory — Alpine.js front-end.
 * Talks to FastAPI /api/* endpoints. Inside HA Ingress, requests are
 * relative to the ingress URL so everything Just Works.
 */

// Field definitions per section. Used for table columns AND the edit modal.
const SECTION_FIELDS = {
  hardware: [
    { key: 'id',       label: 'ID',       table: true },
    { key: 'name',     label: 'Name',     table: true },
    { key: 'type',     label: 'Type',     table: true, type: 'select',
      options: ['server','nas','iot','network','av','compute','sensor','hub','other'] },
    { key: 'location', label: 'Location', table: true },
    { key: 'vendor',   label: 'Vendor' },
    { key: 'model',    label: 'Model' },
    { key: 'specs',    label: 'Specs',    type: 'textarea' },
    { key: 'role',     label: 'Role',     table: true },
    { key: 'ip',       label: 'IP' },
    { key: 'mac',      label: 'MAC' },
    { key: 'purchased',label: 'Purchased' },
    { key: 'notes',    label: 'Notes',    type: 'textarea' },
    { key: 'tags',     label: 'Tags',     type: 'tags' },
  ],
  applications: [
    { key: 'id',       label: 'ID',       table: true },
    { key: 'name',     label: 'Name',     table: true },
    { key: 'type',     label: 'Type',     table: true, type: 'select',
      options: ['ha_addon','container','native','vm','saas','other'] },
    { key: 'runs_on',  label: 'Runs on',  table: true },
    { key: 'url',      label: 'URL' },
    { key: 'version',  label: 'Version' },
    { key: 'purpose',  label: 'Purpose',  table: true },
    { key: 'notes',    label: 'Notes',    type: 'textarea' },
    { key: 'tags',     label: 'Tags',     type: 'tags' },
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

// API base. Inside HA Ingress, ingress rewrites paths, so a relative base works.
const API = './api';

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

    tabs: [
      { id: 'overview',     label: 'Overview' },
      { id: 'hardware',     label: 'Hardware' },
      { id: 'network',      label: 'Network' },
      { id: 'applications', label: 'Applications' },
      { id: 'integrations', label: 'Integrations' },
      { id: 'yaml',         label: 'YAML' },
    ],

    flatSections: [
      { key: 'hardware',     label: 'Hardware',     cols: tableCols('hardware') },
      { key: 'applications', label: 'Applications', cols: tableCols('applications') },
      { key: 'integrations', label: 'Integrations', cols: tableCols('integrations') },
    ],

    networkSections: [
      { key: 'subnets', label: 'Subnets', cols: tableCols('network/subnets') },
      { key: 'vlans',   label: 'VLANs',   cols: tableCols('network/vlans') },
      { key: 'hosts',   label: 'Hosts',   cols: tableCols('network/hosts') },
    ],

    async init() {
      await this.reload();
      this.$watch('tab', t => { if (t === 'overview') this.$nextTick(() => this.renderGraph()); });
      this.$watch('inv', () => { if (this.tab === 'overview') this.renderGraph(); }, { deep: true });
    },

    async reload() {
      try {
        const res = await fetch(`${API}/inventory`);
        this.inv = await res.json();
        const rawRes = await fetch(`${API}/inventory/raw`);
        this.rawYaml = await rawRes.text();
        if (this.tab === 'overview') this.$nextTick(() => this.renderGraph());
      } catch (e) {
        console.error(e);
      }
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
        // strip empties so YAML stays tidy
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
          color: { background: palette[h.type] || palette.other, border: '#0f172a' },
          font: { color: 'white' },
        });
      });

      (this.inv.applications || []).forEach(a => {
        nodes.push({
          id: 'app:' + a.id,
          label: a.name,
          title: [a.type, a.purpose].filter(Boolean).join(' • '),
          shape: 'ellipse',
          color: { background: '#ede9fe', border: '#7c3aed' },
        });
        if (a.runs_on) {
          edges.push({ from: 'app:' + a.id, to: 'hw:' + a.runs_on, dashes: true });
        }
      });

      (this.inv.network?.hosts || []).forEach(h => {
        if (h.hardware_id) {
          // host edges already implicit via hardware; skip duplicate node
        }
      });

      (this.inv.integrations || []).forEach(i => {
        nodes.push({
          id: 'int:' + i.id,
          label: i.name,
          title: [i.type, i.purpose].filter(Boolean).join(' • '),
          shape: 'diamond',
          color: { background: '#fef3c7', border: '#d97706' },
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
        edges: { color: { color: '#94a3b8' }, smooth: { type: 'continuous' } },
      };

      if (this.graphNetwork) this.graphNetwork.destroy();
      this.graphNetwork = new vis.Network(container, data, options);
    },
  };
}

window.app = app;
