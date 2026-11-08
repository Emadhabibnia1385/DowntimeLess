from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

ROLES = "^(relay|exit|panel|panel_only|other)$"
PERMS = "^(read|safe|full)$"
FLEETS = "^(emad|mobin|shared)$"


class Latest(BaseModel):
    cpu_pct: Optional[float] = None
    steal_pct: Optional[float] = None
    ram_pct: Optional[float] = None
    disk_pct: Optional[float] = None
    rx_bps: Optional[float] = None
    tx_bps: Optional[float] = None
    uptime_s: Optional[int] = None
    load1: Optional[float] = None
    tcp_retrans_pct: Optional[float] = None
    conntrack_pct: Optional[float] = None
    cpu_cores: Optional[int] = None
    ram_total_mb: Optional[float] = None
    ram_used_mb: Optional[float] = None
    disk_total_gb: Optional[float] = None
    disk_used_gb: Optional[float] = None
    reboot_required: bool = False
    failed_units: List[str] = []


class ServerOut(BaseModel):
    id: int
    name: str
    alias: str
    role: str
    fleet: str = "emad"
    permission: str
    status: str
    last_seen: Optional[int]
    hostname: Optional[str]
    public_ip: Optional[str]
    country: Optional[str]
    city: Optional[str]
    org: Optional[str]
    agent_version: Optional[str]
    agent_outdated: bool = False
    latest: Latest


class ServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    alias: str = Field(default="", max_length=64)
    role: str = Field(default="other", pattern=ROLES)
    fleet: str = Field(default="emad", pattern=FLEETS)


class ServerPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    alias: Optional[str] = Field(default=None, max_length=64)
    role: Optional[str] = Field(default=None, pattern=ROLES)
    fleet: Optional[str] = Field(default=None, pattern=FLEETS)
    permission: Optional[str] = Field(default=None, pattern=PERMS)


class ServerCreated(BaseModel):
    server: ServerOut
    install_command: str


class MetricPoint(BaseModel):
    ts: int
    cpu: Optional[float]
    ram_pct: Optional[float]
    disk_pct: Optional[float]
    rx_bps: Optional[float]
    tx_bps: Optional[float]
    rx_bytes: int
    tx_bytes: int


class MetricsOut(BaseModel):
    range: str
    points: List[MetricPoint]
    rx_total: int
    tx_total: int


class JobCreate(BaseModel):
    kind: str
    args: Dict[str, Any] = {}


class JobOut(BaseModel):
    id: int
    kind: str
    args: Dict[str, Any]
    status: str
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: int
    done_at: Optional[int]
