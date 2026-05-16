"""Seed data populated the first time the inventory is loaded.

Pre-fills facts already known about Roel's homelab (Starkillerbase). Edit
freely in the UI afterwards — the seed only runs when the inventory is empty.
"""

from .schemas import (
    Inventory,
    Hardware,
    Application,
    Integration,
    Network,
    Host,
)


def initial_inventory() -> Inventory:
    return Inventory(
        version=1,
        meta={
            "instance_name": "Starkillerbase",
            "timezone": "Europe/Amsterdam",
            "ui_language": "nl",
        },
        hardware=[
            Hardware(
                id="starkillerbase",
                name="Starkillerbase",
                type="server",
                role="Home Assistant OS host",
                notes="Main HAOS instance running Home Assistant + add-ons.",
                tags=["home-assistant", "haos"],
            ),
            Hardware(
                id="living-room-tv",
                name="Philips Android TV (living room)",
                type="av",
                location="Living room",
                vendor="Philips",
                role="Display + Android TV apps",
                notes=(
                    "Exposed in HA as BOTH media_player.tv and media_player.a_tv. "
                    "TV speakers unused — audio routed via receiver."
                ),
                tags=["tv", "android-tv"],
            ),
            Hardware(
                id="home-cinema-receiver",
                name="Home Cinema Receiver",
                type="av",
                location="Living room",
                role="A/V receiver",
                notes=(
                    "IR-controlled, no state feedback to HA. Drives Harman Kardon "
                    "speakers; TV audio passes through this receiver."
                ),
                tags=["av", "ir-controlled"],
            ),
            Hardware(
                id="harman-kardon-speakers",
                name="Harman Kardon speakers",
                type="av",
                location="Living room",
                vendor="Harman Kardon",
                role="Main living-room speakers",
                notes="Driven by the home cinema receiver.",
                tags=["audio"],
            ),
            Hardware(
                id="apple-tv-puck",
                name="Apple TV (physical puck)",
                type="av",
                location="Living room",
                vendor="Apple",
                role="Streaming box",
                notes="NOT exposed in HA. Part of AV chain into the receiver.",
                tags=["apple-tv"],
            ),
            Hardware(
                id="homepods",
                name="HomePods",
                type="av",
                vendor="Apple",
                role="Smart speakers",
                notes=(
                    "Reached via Music Assistant proxy — direct apple_tv platform "
                    "fails to decode Piper TTS audio."
                ),
                tags=["audio", "tts-target"],
            ),
        ],
        network=Network(
            hosts=[
                Host(
                    id="host-starkillerbase",
                    hostname="starkillerbase.local",
                    hardware_id="starkillerbase",
                    purpose="Home Assistant",
                ),
            ],
        ),
        applications=[
            Application(
                id="home-assistant",
                name="Home Assistant",
                type="native",
                runs_on="starkillerbase",
                url="http://homeassistant.local:8123",
                purpose="Home automation hub",
                tags=["core"],
            ),
            Application(
                id="music-assistant",
                name="Music Assistant",
                type="ha_addon",
                runs_on="starkillerbase",
                purpose="Music streaming + TTS bridge to HomePods/AirPlay",
                notes="Used as proxy for HomePod TTS playback.",
                tags=["audio", "tts"],
            ),
            Application(
                id="piper-tts",
                name="Piper TTS (Wyoming)",
                type="ha_addon",
                runs_on="starkillerbase",
                purpose="Local TTS — voice nl_BE-nathalie-medium",
                notes=(
                    "Belgian Dutch Nathalie voice, picked after trying MLS and Ronnie."
                ),
                tags=["tts", "voice"],
            ),
            Application(
                id="finance-dashboard",
                name="Finance Dashboard",
                type="ha_addon",
                runs_on="starkillerbase",
                purpose="Personal finance: Rabobank CSV, budgets, VGN CAO projection",
                tags=["self-hosted"],
            ),
            Application(
                id="homelab-inventory",
                name="Homelab Inventory",
                type="ha_addon",
                runs_on="starkillerbase",
                purpose="This add-on — homelab inventory database",
                tags=["self-hosted", "documentation"],
            ),
        ],
        integrations=[
            Integration(
                id="apple-tv-integration",
                name="apple_tv",
                type="ha_integration",
                purpose="Apple TV / HomePod control",
                notes="Direct platform fails for Piper TTS — use Music Assistant.",
            ),
            Integration(
                id="wyoming",
                name="Wyoming",
                type="ha_integration",
                purpose="Piper TTS / Whisper STT protocol bridge",
            ),
        ],
    )
