from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

ROLES = "^(relay|exit|panel|panel_only|other)$"
PERMS = "^(read|safe|full)$"


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
    load5: Optional[float] = None
    load15: Optional[float] = None
    swap_total_mb: Optional[float] = None
    swap_used_mb: Optional[float] = None
    swap_pct: Optional[float] = None
    tcp_established: Optional[int] = None


class SystemInfo(BaseModel):
    os: Optional[str] = None
    kernel: Optional[str] = None
    cpu_model: Optional[str] = None
    cpu_cores: Optional[int] = None
    boot_ts: Optional[int] = None
    ipv6: Optional[str] = None


class ServerOut(BaseModel):
    id: int
    name: str
    alias: str
    role: str
    category_id: Optional[int] = None
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
    acct_on: bool = False
    quota_gb: Optional[float] = None
    quota_reset_day: Optional[int] = None
    latest: Latest
    system: SystemInfo = SystemInfo()


class ServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    alias: str = Field(default="", max_length=64)
    role: str = Field(default="other", pattern=ROLES)
    category_id: Optional[int] = None


class ServerPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    alias: Optional[str] = Field(default=None, max_length=64)
    role: Optional[str] = Field(default=None, pattern=ROLES)
    category_id: Optional[int] = None  # null clears it; leave it out to keep it
    permission: Optional[str] = Field(default=None, pattern=PERMS)
    acct_on: Optional[bool] = None
    quota_gb: Optional[float] = Field(default=None, gt=0, le=1_000_000)  # null clears it
    quota_reset_day: Optional[int] = Field(default=None, ge=1, le=31)  # null clears it


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
    steal: Optional[float] = None
    load1: Optional[float] = None
    swap_pct: Optional[float] = None
    retrans: Optional[float] = None
    conntrack: Optional[float] = None
    conns: Optional[float] = None


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
