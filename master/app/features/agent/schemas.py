from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EnrollRequest(BaseModel):
    token: str = Field(min_length=8, max_length=128)
    hostname: str = Field(default="", max_length=128)


class EnrollResult(BaseModel):
    agent_key: str


class JobDone(BaseModel):
    id: int
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class Report(BaseModel):
    model_config = ConfigDict(extra="allow")  # new agents may send fields an older master ignores
    agent_version: str = ""
    hostname: str = ""
    public_ip: Optional[str] = None
    geo: Optional[Dict[str, Any]] = None
    cpu_cores: Optional[int] = None
    cpu_pct: Optional[float] = None
    steal_pct: Optional[float] = None
    ram_total_mb: Optional[float] = None
    ram_avail_mb: Optional[float] = None
    disk_total_gb: Optional[float] = None
    disk_used_gb: Optional[float] = None
    net: Optional[Dict[str, Any]] = None
    tcp_retrans_pct: Optional[float] = None
    conntrack_pct: Optional[float] = None
    ping: List[Dict[str, Any]] = []
    jobs_done: List[JobDone] = []


class PingTarget(BaseModel):
    target: str
    tcp_port: Optional[int] = None


class JobToRun(BaseModel):
    id: int
    kind: str
    args: Dict[str, Any]


class ReportResult(BaseModel):
    interval_s: int
    permission: str
    acct_peers: List[str] = []
    ping_targets: List[PingTarget]
    jobs: List[JobToRun]
