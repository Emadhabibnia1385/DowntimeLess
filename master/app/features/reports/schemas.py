from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---- briefing ----
class RoleCount(BaseModel):
    role: str
    online: int
    offline: int
    pending: int


class CategoryCount(BaseModel):
    category: str
    online: int
    offline: int
    pending: int


class FleetBrief(BaseModel):
    total: int
    online: int
    offline: int
    pending: int
    by_role: List[RoleCount]
    by_category: List[CategoryCount]


class IssueBrief(BaseModel):
    severity: str
    server_id: Optional[int]
    server: Optional[str]
    code: str
    title: str
    evidence: Dict[str, Any]
    suggestion: str
    recent_24h: int


class IssuesBrief(BaseModel):
    critical: int
    warning: int
    info: int
    items: List[IssueBrief]
    truncated: bool


class RecurringBrief(BaseModel):
    server: Optional[str]
    code: Optional[str]
    occurrences: int
    total_s: int
    active_now: bool
    flapping: bool


class PathProblem(BaseModel):
    kind: str
    server: Optional[str]
    detail: str
    source: str


class HealthAttention(BaseModel):
    server_id: int
    name: str
    role: str
    score: Optional[int]
    band: str
    gates: List[str]
    top_penalty: Optional[str]


class HealthBrief(BaseModel):
    counts: Dict[str, int]
    attention: List[HealthAttention]
    truncated: bool


class ByteSplit(BaseModel):
    rx: int
    tx: int
    total: int
    relay: int
    exit: int
    other: int


class ServerBytes(BaseModel):
    server_id: int
    server: str
    role: str
    rx: int
    tx: int
    total: int


class LinkPairBytes(BaseModel):
    server: str
    server_role: str
    peer: str
    in_bytes: int
    out_bytes: int


class TrafficBrief(BaseModel):
    today: ByteSplit
    yesterday: ByteSplit
    last_7d: ByteSplit
    top_servers: List[ServerBytes]
    pairs_7d: List[LinkPairBytes]
    link_counting: bool


class QuotaRow(BaseModel):
    server_id: int
    server_name: str
    quota_gb: float
    used_gb: float
    used_pct: float
    per_day_gb: Optional[float]
    days_left: Optional[float]
    resets_in_days: float
    runs_out: bool
    basis: str = "out"  # out, both, or download (upload free on this server)


class CertRisk(BaseModel):
    name: str
    server: Optional[str]
    days_left: Optional[int]
    level: str
    auto_renew: str
    error: Optional[str]


class AgentsOutdated(BaseModel):
    latest: Optional[str]
    servers: List[str]


class ChangeBrief(BaseModel):
    ts: int
    server: Optional[str]
    kind: str
    title: str


class CheckStep(BaseModel):
    code: str
    severity: str
    count: int
    servers: List[str]
    first_check: Optional[str]
    playbook: Optional[str]
    why: str


class AckBrief(BaseModel):
    severity: str
    server_id: Optional[int]
    server: Optional[str]
    code: str
    title: str
    mode: Optional[str]
    until: Optional[int]
    by: Optional[str]
    note: Optional[str]


class HostProblem(BaseModel):
    server: Optional[str]
    code: str
    severity: str
    detail: str


class HostChecksBrief(BaseModel):
    reporting: int
    without: List[str]
    problems: List[HostProblem]


class ResellerBrief(BaseModel):
    name: str
    used_pct: float
    hours_left: Optional[float]
    level: str


class PanelBrief(BaseModel):
    server: str
    version: Optional[str]
    nodes_total: int
    connected: int
    disabled: int
    not_connected: List[str]
    dropped: List[str]
    users_last_hour: Optional[int]
    resellers_near_quota: List[ResellerBrief]
    user_status: Optional[Dict[str, int]]
    inbounds_without_group: List[str]
    errors: List[str]


class Briefing(BaseModel):
    generated_at: int
    detail: str
    timezone_note: str
    fleet: FleetBrief
    issues: IssuesBrief
    recurring_24h: List[RecurringBrief]
    path_problems: List[PathProblem]
    health: HealthBrief
    traffic: TrafficBrief
    quota: Optional[List[QuotaRow]]
    certs_at_risk: List[CertRisk]
    agents_outdated: AgentsOutdated
    changes_24h: List[ChangeBrief]
    issue_events_24h: int
    check_first: List[CheckStep]
    acknowledged: List[AckBrief] = []
    host_checks: HostChecksBrief
    panel: List[PanelBrief]
    not_measured: List[str]


# ---- playbooks ----
class Playbook(BaseModel):
    code: str
    theme: str
    title: str
    summary_fa: str
    detector: str
    causes: List[str]
    checks: List[str]
    fixes: List[str]
    never: List[str]
    source: List[str]


class PlaybookItem(BaseModel):
    code: str
    theme: str
    title: str
    summary_fa: str
    detector: str
    # lang=fa only, and only for the codes that have a guide for people
    title_fa: Optional[str] = None
    meaning_fa: Optional[str] = None
    fix_cmd_fa: Optional[str] = None  # the first command of the guide's fixes, shown to copy beside the issue


class PlaybookList(BaseModel):
    principles: List[str]
    playbooks: List[PlaybookItem]


class GuideStep(BaseModel):
    text: str
    cmd: Optional[str] = None  # shown for the person to copy and run; the panel never runs it


class GuideFa(BaseModel):
    code: str
    title: str
    meaning: str
    why: str
    checks: List[GuideStep]
    fixes: List[GuideStep]
    fixed_when: List[str]
    never: List[str]


class PlaybookOut(BaseModel):
    matched: bool
    playbook: Playbook
    guide_fa: Optional[GuideFa] = None  # lang=fa: the guide for people (the generic one when none is written)


# ---- health ----
class Gate(BaseModel):
    key: str
    detail: str


class Penalty(BaseModel):
    key: str
    points: int
    max: int
    detail: str


class ServerHealth(BaseModel):
    server_id: int
    name: str
    role: str
    country: Optional[str]
    category_id: Optional[int]
    status: str
    variant: str
    score: Optional[int]
    band: str
    gates: List[Gate]
    penalties: List[Penalty]
    open_issues: int
    acked_issues: int = 0
    not_measured: List[str]


class HealthOut(BaseModel):
    generated_at: int
    counts: Dict[str, int]
    servers: List[ServerHealth]
    description: str
    weights: Dict[str, Dict[str, int]]
    not_measured: Dict[str, List[str]]
    quota_measured: bool


# ---- changes ----
class EventOut(BaseModel):
    id: int
    ts: int
    server_id: Optional[int]
    server: Optional[str]
    kind: str
    title: str
    detail: Dict[str, Any]


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    server_id: Optional[int] = None


class ChangesOut(BaseModel):
    since: int
    until: int
    events: List[EventOut]
    truncated: bool


# ---- daily ----
class DailyIncidents(BaseModel):
    opened: int
    closed: int
    critical_opened: int
    still_open: int
    mttr_s: Optional[int]
    previous_opened: int
    previous_closed: int


class AvailabilityRow(BaseModel):
    server_id: int
    server: str
    role: str
    availability_pct: float
    down_s: int
    outages: int
    samples: int
    observed_s: int


class DailyAvailability(BaseModel):
    fleet_pct: Optional[float]
    below_100: List[AvailabilityRow]


class DailyTraffic(BaseModel):
    total: int
    previous_total: int
    change_pct: Optional[float]
    relay: int
    exit: int
    other: int


class TopIssue(BaseModel):
    server: str
    code: str
    occurrences: int
    total_s: int
    active_now: bool


class DailyOut(BaseModel):
    since: int
    until: int
    previous_since: int
    incidents: DailyIncidents
    availability: DailyAvailability
    traffic: DailyTraffic
    top_issues: List[TopIssue]
    health: Dict[str, int]
    changes: List[ChangeBrief]


# ---- incidents report ----
class IncTotals(BaseModel):
    opened: int
    closed: int
    still_open: int
    critical_opened: int
    mttr_s: Optional[int]


class IncByCode(BaseModel):
    code: str
    incidents: int
    total_s: int
    resolved: int
    mttr_s: Optional[int]


class IncByServer(BaseModel):
    server: str
    server_id: Optional[int]
    incidents: int
    total_s: int


class IncFlapping(BaseModel):
    key: str
    code: str
    server: str
    occurrences: int
    total_s: int
    severity: Optional[str]
    active_now: bool


class IncLongest(BaseModel):
    server: Optional[str]
    server_id: Optional[int]
    code: Optional[str]
    severity: Optional[str]
    opened_at: int
    closed_at: Optional[int]
    duration_s: int


class IncidentsReport(BaseModel):
    since: int
    until: int
    retention_days: int
    totals: IncTotals
    by_code: List[IncByCode]
    by_server: List[IncByServer]
    flapping: List[IncFlapping]
    longest: List[IncLongest]
    truncated: bool


# ---- traffic report ----
class DayBytes(BaseModel):
    day_start: int
    rx: int
    tx: int
    total: int


class PeakDay(BaseModel):
    day_start: int
    bytes: int


class PeakHour(BaseModel):
    hour_start: int
    bytes: int


class TrafficReport(BaseModel):
    since: int
    until: int
    fleet: ByteSplit
    servers: List[ServerBytes]
    daily: List[DayBytes]
    peak_day: Optional[PeakDay]
    peak_hour: Optional[PeakHour]
    link_pairs: List[LinkPairBytes]
    truncated: bool
    note: str


# ---- availability ----
class AvailabilityReport(BaseModel):
    since: int
    until: int
    fleet_availability_pct: Optional[float]
    servers: List[AvailabilityRow]
    truncated: bool
    method: str


# ---- capacity ----
class CapacityRow(BaseModel):
    server_id: int
    server: str
    role: str
    category_id: Optional[int]
    cores: Optional[int]
    peak_hour: int
    cpu_peak: Optional[float]
    steal_peak: Optional[float]
    load1_peak: Optional[float]
    load_per_core_peak: Optional[float]
    conntrack_peak: Optional[float]
    ram_peak: Optional[float]
    traffic_bytes: int
    traffic_growth_pct: Optional[float]
    cpu_growth_pct: Optional[float]
    sibling_group: Optional[str]
    vs_sibling_median: Optional[float]
    imbalance: bool


class CapacityReport(BaseModel):
    since: int
    until: int
    servers: List[CapacityRow]
    truncated: bool
    note: str


# ---- relays ----
class RelayPair(BaseModel):
    relay_id: int
    relay: str
    exit_id: int
    exit: str
    loss_pct: Optional[float]  # ICMP
    rtt_ms: Optional[float]
    samples: int
    tcp_fail_pct: Optional[float] = None  # share of TCP connections to proven ports that failed
    tcp_rtt_ms: Optional[float] = None
    tcp_samples: int = 0
    tls_failed: int = 0  # TLS handshakes that failed after the TCP connection was accepted
    verdict: str
    in_bytes: Optional[int]
    out_bytes: Optional[int]


class RelaysReport(BaseModel):
    since: int
    until: int
    ping_window_s: int
    pairs: List[RelayPair]
    truncated: bool
    problems: int
    note: str
