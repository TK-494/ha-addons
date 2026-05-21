"""Pydantic models for the homelab inventory.

Each top-level category is a list of records. Records are dicts with a
required `id` (slug-style, used as foreign key) and `name`. Everything else
is optional and free-form, so the schema can grow without breaking old data.
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


HardwareType = Literal[
    "server", "nas", "iot", "network", "av", "compute", "hub", "other"
]
AppType = Literal["ha_addon", "container", "native", "vm", "saas", "other"]
IntegrationType = Literal["ha_integration", "cloud", "api", "service", "other"]

# Sensors are their own section now. Kinds match HA's device_class values
# wherever possible so discovery classification can pass them straight through.
SensorKind = Literal[
    "motion", "occupancy", "presence",
    "door", "window", "opening", "garage_door",
    "contact",
    "temperature", "humidity", "pressure", "illuminance",
    "moisture", "water", "leak",
    "smoke", "gas", "co", "co2",
    "vibration", "tamper", "sound",
    "battery", "power", "energy",
    "other",
]


class Hardware(BaseModel):
    id: str
    name: str
    type: HardwareType = "other"
    location: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    specs: Optional[str] = None
    role: Optional[str] = None
    ip: Optional[str] = None
    mac: Optional[str] = None
    purchased: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    ha_device_id: Optional[str] = None
    ha_entity_id: Optional[str] = None


class Subnet(BaseModel):
    id: str
    name: str
    cidr: Optional[str] = None
    vlan_id: Optional[int] = None
    gateway: Optional[str] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None


class Vlan(BaseModel):
    id: str
    name: str
    vlan_id: Optional[int] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None


class Host(BaseModel):
    id: str
    hostname: str
    ip: Optional[str] = None
    hardware_id: Optional[str] = None  # links to Hardware.id
    subnet_id: Optional[str] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None


class Network(BaseModel):
    subnets: List[Subnet] = Field(default_factory=list)
    vlans: List[Vlan] = Field(default_factory=list)
    hosts: List[Host] = Field(default_factory=list)


class Application(BaseModel):
    id: str
    name: str
    type: AppType = "other"
    runs_on: Optional[str] = None  # hardware_id
    url: Optional[str] = None
    version: Optional[str] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    ha_entity_id: Optional[str] = None


class Sensor(BaseModel):
    """A discrete sensor — typically maps to one HA device with one primary entity."""
    id: str
    name: str
    kind: SensorKind = "other"
    location: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    hardware_id: Optional[str] = None      # links to Hardware.id when the sensor is part of a larger unit (e.g. an alarm hub)
    ha_device_id: Optional[str] = None
    ha_entity_id: Optional[str] = None     # primary entity (the one whose state = the sensor reading)
    battery_powered: bool = False
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class Integration(BaseModel):
    id: str
    name: str
    type: IntegrationType = "other"
    purpose: Optional[str] = None
    account: Optional[str] = None  # username/email, NOT secrets
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class Inventory(BaseModel):
    """Full inventory document — what lives in infrastructure.yaml."""
    version: int = 1
    hardware: List[Hardware] = Field(default_factory=list)
    network: Network = Field(default_factory=Network)
    applications: List[Application] = Field(default_factory=list)
    sensors: List[Sensor] = Field(default_factory=list)
    integrations: List[Integration] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
