# Finance Dashboard — Documentation

## How it works

Single FastAPI container that serves both the React frontend (built as static files) and the JSON API. SQLite database persisted in `/data/finance.db` (HA-managed volume).

## Configuration

This add-on currently has no configurable options — defaults work out of the box.

## Importing a Rabobank CSV

1. Log in to Mijn Rabobank → Overzicht → Downloaden → CSV
2. In the add-on, go to **Importeren** and drop the file
3. Duplicate transactions are detected via SHA-256 hash, so re-importing the same period is safe

## Editing VGN CAO salary scales

The add-on seeds approximate 2024 FWG salary scales. To update them:

1. Go to **CAO Groei** → ✏️ Schalen bewerken
2. Pick a scale, edit the periodic step values, save

## Data backup

Your SQLite DB lives in the add-on's `/data` directory. It's included in Home Assistant's full backups automatically.
