from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class MissingPort(BaseModel):
    proto: str
    port: int
    proc: Optional[str] = None
    missing_reports: int
    alerting: bool


class ListenerSummary(BaseModel):
    current: int
    baseline: int
    learning: int
    missing: List[MissingPort]


class UnitRow(BaseModel):
    name: str
    enabled: bool
    active: Optional[str] = None
    sub: Optional[str] = None
    restarts: Optional[int] = None
    restarts_10m: int
    tunnel: bool


class ContainerRow(BaseModel):
    name: str
    image: Optional[str] = None
    state: Optional[str] = None
    health: Optional[str] = None
    restarts: Optional[int] = None
    policy: Optional[str] = None
    retired: bool


class NftSummary(BaseModel):
    relay_dnat: bool
    dnat_rules: Optional[int] = None
    tables: Optional[int] = None
    ip_forward: Optional[int] = None
    had_dnat: bool


class ConntrackLive(BaseModel):
    module_loaded: bool
    count: Optional[int] = None
    max: Optional[int] = None
    pct: Optional[float] = None
    tcp_established_timeout: Optional[int] = None
    insert_failed: Optional[int] = None
    drop: Optional[int] = None
    early_drop: Optional[int] = None


class KernelFlags(BaseModel):
    congestion: Optional[str] = None
    qdisc: Optional[str] = None
    ip_forward: Optional[int] = None
    oom_kill: Optional[int] = None
    ntp_synced: Optional[bool] = None
    inode_pct: Optional[float] = None
    journal_mb: Optional[float] = None
    mtu_probing: Optional[int] = None
    swappiness: Optional[int] = None


class AptState(BaseModel):
    dpkg_audit: Optional[int] = None
    reboot_required_pkgs: Optional[int] = None
    held_docker: Optional[bool] = None


class SecurityState(BaseModel):
    ufw: Optional[str] = None
    fail2ban: Optional[str] = None
    password_auth: Optional[bool] = None
    sshd_ports: Optional[List[int]] = None


class HostHealth(BaseModel):
    server_id: int
    has_checks: bool
    agent_version: Optional[str] = None
    checks_error: List[str]
    listeners: Optional[ListenerSummary] = None
    units: Optional[List[UnitRow]] = None
    containers: Optional[List[ContainerRow]] = None
    nft: Optional[NftSummary] = None
    conntrack: Optional[ConntrackLive] = None
    kernel: Optional[KernelFlags] = None
    apt: Optional[AptState] = None
    security: Optional[SecurityState] = None


class ListenerDrop(BaseModel):
    proto: Literal["tcp", "udp"]
    port: int = Field(ge=1, le=65535)


class IgnoreSet(BaseModel):
    kind: Literal["container", "node", "inbound", "dnat"]
    name: str = Field(default="", max_length=128)
    ignored: bool = True


class IgnoreOut(BaseModel):
    kind: str
    name: str
    ignored: bool


class PanelNode(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    port: Optional[int] = None
    status: str
    message: Optional[str] = None
    enabled: bool
    ignored: bool
    users_last: Optional[int] = None
    bytes_last: Optional[int] = None
    users_median: Optional[float] = None
    bytes_median: Optional[int] = None
    users_pct: Optional[float] = None
    bytes_pct: Optional[float] = None
    others_pct: Optional[float] = None
    dropped: bool
    down_s: Optional[int] = None
    unavailable_10m: Optional[int] = None


class Reseller(BaseModel):
    name: str
    used: int
    limit: int
    used_pct: float
    per_hour: Optional[int] = None
    hours_left: Optional[float] = None
    level: str


class InboundTag(BaseModel):
    tag: str
    ignored: bool


class PanelHost(BaseModel):
    server_id: int
    server_name: str
    reported_at: Optional[int] = None
    version: Optional[str] = None
    errors: List[str]
    panel_error: Optional[str] = None
    available: bool
    hour_start: Optional[int] = None
    nodes: List[PanelNode]
    resellers: List[Reseller]
    user_status: Optional[Dict[str, int]] = None
    inbounds_without_group: List[InboundTag]


class PanelOut(BaseModel):
    generated_at: int
    reseller_warn: float
    reseller_crit: float
    node_drop_pct: float
    panels: List[PanelHost]
