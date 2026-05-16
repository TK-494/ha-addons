# ha-addons — Roel's HA Add-ons

This repo is a [Home Assistant custom add-on repository](https://developers.home-assistant.io/docs/add-ons/repository). It holds the source for self-hosted apps that get installed as add-ons on Starkillerbase (HAOS).

## Add-ons

| Add-on | Description |
|---|---|
| [`finance-dashboard/`](finance-dashboard/) | Personal finance dashboard — Rabobank CSV analysis, budgets, VGN CAO salary projection |
| [`homelab-inventory/`](homelab-inventory/) | Living homelab inventory — hardware, network, apps, integrations. YAML-backed with topology graph. |

## Installing in Home Assistant

1. Settings → Add-ons → ⋮ (top right) → **Repositories**
2. Paste: `https://github.com/TK-494/ha-addons`
3. The add-ons appear under "Roel's Add-ons" — install + start
4. With `ingress: true`, they show up in the HA sidebar with HA's auth

## Updating

```bash
# locally
git add -A && git commit -m "..." && git push

# on HA (via SSH host shell)
ha addons rebuild local_<slug>
```

Or click **Rebuild** on the add-on detail page in HA UI.

## Layout

```
.
├── repository.yaml          # marks this as an HA add-on repo
├── README.md                # this file
├── .gitignore
└── <addon-slug>/            # one folder per add-on
    ├── config.yaml          # HA manifest
    ├── Dockerfile           # multi-stage build
    ├── run.sh               # entrypoint
    ├── README.md            # shown in HA add-on UI
    ├── DOCS.md              # shown in HA UI "Documentation" tab
    ├── docker-compose.yml   # alt deployment for non-HAOS hosts
    └── ...                  # app source
```

New add-ons follow the [`ha-addon-template`](https://github.com/TK-494) scaffold from Roel's Obsidian vault (`30-resources/templates/ha-addon-template/`).
