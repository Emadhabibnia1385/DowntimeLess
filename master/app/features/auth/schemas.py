from typing import List, Optional

from pydantic import BaseModel, Field


class WorkspaceOut(BaseModel):
    id: int
    name: str
    role: str  # my role in it: viewer, operator, admin or owner
    is_personal: bool  # the one I own
    invited_by: Optional[str] = None  # who added me, for a workspace that is not mine


class UserOut(BaseModel):
    id: int
    name: str
    username: Optional[str]
    role: str  # my role in the active workspace
    has_password: bool
    tg_username: Optional[str]
    tg_linked: bool = False  # a Telegram account is linked (it may have no username)
    workspace: WorkspaceOut  # the workspace this request acts in
    is_panel_owner: bool = False  # owner of workspace 1: the only one who adds new people


class SwitchWorkspace(BaseModel):
    workspace_id: int


class StartResult(BaseModel):
    challenge_id: int
    deep_link: str
    poll_secret: str
    expires_in: int


class PollRequest(BaseModel):
    challenge_id: int
    poll_secret: str


class PollResult(BaseModel):
    status: str
    user: Optional[UserOut] = None


class WebAppRequest(BaseModel):
    init_data: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=512)
    password2: str = Field(min_length=1, max_length=512)


class RegistrationOut(BaseModel):
    open: bool


class RegistrationIn(BaseModel):
    open: bool


class LinkStart(BaseModel):
    link_id: int
    deep_link: str
    expires_in: int


class LinkTelegram(BaseModel):
    id: int
    username: Optional[str] = None
    name: str = ""


class MergeWorkspace(BaseModel):
    workspace_id: int
    name: str
    role: str  # the other account's role there
    survivor_role: Optional[str] = None  # the surviving account's role there before the merge
    result_role: str
    owned: bool  # the other account owns it: ownership moves


class MergeOther(BaseModel):
    username: Optional[str] = None
    name: str = ""
    has_password: bool
    tg_username: Optional[str] = None


class MergePlan(BaseModel):
    survivor: str  # "this": the signed-in account stays; "telegram": the Telegram account's account stays
    other: MergeOther
    workspaces: List[MergeWorkspace]
    api_keys: int
    moves_password: bool
    keeps_panel_owner: bool
    fingerprint: str  # send it back with the confirmation: the merge happens only if nothing changed since


class LinkView(BaseModel):
    link_id: int
    status: str  # pending, seen, confirmed, done, denied, expired
    expires_at: int
    telegram: Optional[LinkTelegram] = None
    merge: Optional[MergePlan] = None


class LinkConfirm(BaseModel):
    merge: bool = False
    fingerprint: Optional[str] = Field(default=None, max_length=64)


class LinkDone(BaseModel):
    merged: bool
    claimed_workspaces: int
    user: UserOut


class PasswordRequest(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=64)
    password: str = Field(max_length=256)
    current_password: Optional[str] = Field(default=None, max_length=256)
