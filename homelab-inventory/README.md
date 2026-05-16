# Homelab Inventory

Living database of homelab hardware, network, applications and integrations.

- 🖥️ Hardware: servers, NAS, IoT, network gear, AV
- 🌐 Network: subnets, VLANs, host/IP assignments
- 📦 Applications: HA add-ons, containers, native services
- 🔌 Integrations: HA integrations, cloud accounts (names only — no secrets)
- 🧭 Visual topology graph linking apps → hardware
- 📝 Raw YAML editor when you want to bulk-edit

All data lives in `/data/infrastructure.yaml` (HA persistent volume). The
add-on keeps a rolling backup of the last 10 saves under `/data/backups/`.

## Use

1. Open the add-on from the HA sidebar (icon: server-network)
2. Browse the **Overview** tab for the topology graph
3. Click **+ Add** on any tab to add a hardware item, app, integration, etc.
4. Click any row to edit. Edits save immediately and are written back to YAML.
5. Use the **YAML** tab for power-user bulk edits — invalid YAML is rejected.
