# Homelab Inventory — Documentation

## How it works

Single FastAPI container that serves both the static frontend (HTML + Alpine.js + Tailwind via CDN + vis-network for the topology graph) and a JSON API. Data is persisted as YAML at `/data/infrastructure.yaml` — a Home Assistant managed volume that's included in HA's full backups.

No SQLite, no database server. The YAML file is the source of truth and is human-readable, diffable, and trivial to back up out-of-band.

## Schema

Top-level keys in `infrastructure.yaml`:

- `version` — schema version (integer)
- `meta` — free-form key/value (instance name, timezone, etc.)
- `hardware` — list of physical devices
- `network`
  - `subnets` — CIDRs, VLANs, gateways
  - `vlans` — VLAN definitions
  - `hosts` — IP/hostname → hardware mappings
- `applications` — software running on hardware (HA add-ons, containers, native, VMs, SaaS)
- `integrations` — HA integrations, cloud accounts, APIs

Every item has an `id` (slug-style, used as foreign key) and a `name`. Fields like `runs_on` on an application link to a `hardware.id`. The topology graph uses these links to draw edges.

## Configuration

This add-on has no configurable options — defaults work out of the box.

## Backups

- Home Assistant full backups include `/data/infrastructure.yaml` automatically.
- The add-on also keeps a rolling history of the last 10 saves at `/data/backups/infrastructure-YYYYMMDD-HHMMSS.yaml`.
- To copy the live file off the host: `ha addons stdin → tar` is overkill. Easiest is to use the Samba or SSH add-on and `cat /addon_configs/local_homelab-inventory/infrastructure.yaml`.

## Editing outside the UI

Because the data is plain YAML, you can also edit `infrastructure.yaml` directly (via SSH/Samba or the File Editor add-on). Restart the add-on after manual edits, or just open the UI — the next request reloads from disk.

## API

- `GET  /api/inventory` → full document
- `PUT  /api/inventory` → replace whole document (JSON body)
- `GET  /api/inventory/raw` → raw YAML text
- `PUT  /api/inventory/raw` → replace raw YAML (validated server-side)
- `GET/POST/PUT/DELETE /api/{section}[/{id}]` where section ∈ `hardware`, `applications`, `integrations`
- Same shape under `/api/network/{subnets,vlans,hosts}[/{id}]`
