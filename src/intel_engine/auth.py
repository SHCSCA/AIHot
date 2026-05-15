from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from intel_engine.models import (
    AuditLogRecord,
    PermissionRecord,
    RolePermissionRecord,
    RoleRecord,
    SessionRecord,
    UserPreferenceRecord,
    UserRecord,
    UserRoleRecord,
    utc_now,
)
from intel_engine.settings import Settings


SESSION_COOKIE_NAME = "aihot_session"
SESSION_DAYS = 14
PASSWORD_ITERATIONS = 260_000

PUBLIC_PERMISSIONS = ["feedback.create", "public.read"]

PERMISSIONS: dict[str, tuple[str, str, str]] = {
    "public.read": ("公共阅读", "访问公共情报页面", "public"),
    "feedback.create": ("提交反馈", "提交公共反馈", "public"),
    "ops.dashboard.read": ("工作台", "查看运营工作台", "ops"),
    "sources.read": ("查看信源", "查看信源", "sources"),
    "sources.write": ("管理信源", "新增、编辑、启停信源", "sources"),
    "health.read": ("健康监控", "查看信源健康监控", "health"),
    "quality.read": ("质量校准", "查看质量漏斗和拒绝样本", "quality"),
    "jobs.read": ("查看任务", "查看任务队列", "jobs"),
    "jobs.retry": ("重试任务", "重试抓取任务或手动流水线", "jobs"),
    "events.read": ("查看事件", "查看事件审核", "events"),
    "events.review": ("审核事件", "批准或拒绝事件", "events"),
    "daily.read": ("查看日报", "查看日报发布状态", "daily"),
    "daily.publish": ("发布日报", "生成、发布、取消发布日报", "daily"),
    "strategies.read": ("查看策略", "查看策略版本", "strategies"),
    "strategies.write": ("管理策略", "创建或编辑策略", "strategies"),
    "strategies.activate": ("激活策略", "激活策略版本", "strategies"),
    "feedback.read": ("查看反馈", "查看人工反馈", "feedback"),
    "feedback.update": ("处理反馈", "处理反馈状态", "feedback"),
    "evaluations.read": ("查看评估", "查看评估运行", "evaluations"),
    "evaluations.run": ("执行评估", "创建和执行评估", "evaluations"),
    "users.manage": ("用户管理", "管理用户", "admin"),
    "roles.manage": ("角色权限", "管理角色权限", "admin"),
    "system.manage": ("系统管理", "系统配置和审计", "admin"),
}

OPERATOR_PERMISSIONS = [
    permission
    for permission in PERMISSIONS
    if permission not in {"users.manage", "roles.manage", "system.manage"}
]
ADMIN_PERMISSIONS = list(PERMISSIONS)
ROLE_DEFINITIONS: dict[str, tuple[str, str, bool, list[str]]] = {
    "guest": ("游客", "未登录公共访问者", True, PUBLIC_PERMISSIONS),
    "operator": ("运营", "运营工作台用户", False, OPERATOR_PERMISSIONS),
    "admin": ("管理员", "系统管理员", True, ADMIN_PERMISSIONS),
}


@dataclass(frozen=True)
class Principal:
    user_id: int | None
    username: str
    display_name: str
    roles: list[str]
    permissions: list[str]
    preferences: dict[str, object]
    authenticated: bool
    auth_type: str


def hash_password(password: str, *, salt: str | None = None) -> str:
    resolved_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), resolved_salt.encode("ascii"), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${resolved_salt}${base64.b64encode(digest).decode('ascii')}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), int(iterations))
    return hmac.compare_digest(base64.b64encode(digest).decode("ascii"), expected)


def session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def seed_rbac_defaults(session: Session, *, admin_username: str, admin_password: str) -> None:
    for permission_id, (name, description, group) in PERMISSIONS.items():
        permission = session.get(PermissionRecord, permission_id)
        if permission is None:
            session.add(PermissionRecord(id=permission_id, name=name, description=description, group=group))
        else:
            permission.name = name
            permission.description = description
            permission.group = group

    for role_id, (name, description, locked, permissions) in ROLE_DEFINITIONS.items():
        role = session.get(RoleRecord, role_id)
        if role is None:
            role = RoleRecord(id=role_id, name=name, description=description, locked=locked)
            session.add(role)
        else:
            role.name = name
            role.description = description
            role.locked = locked
        session.flush()
        session.execute(delete(RolePermissionRecord).where(RolePermissionRecord.role_id == role_id))
        for permission_id in permissions:
            session.add(RolePermissionRecord(role_id=role_id, permission_id=permission_id))

    admin = session.scalar(select(UserRecord).where(UserRecord.username == admin_username))
    if admin is None:
        admin = create_user(
            session,
            username=admin_username,
            password=admin_password,
            display_name="系统管理员",
            role_ids=["admin"],
        )
    elif not _user_has_role(session, admin.id, "admin"):
        session.add(UserRoleRecord(user_id=admin.id, role_id="admin"))


def create_user(
    session: Session,
    *,
    username: str,
    password: str,
    display_name: str | None = None,
    email: str | None = None,
    role_ids: list[str] | None = None,
    status: str = "active",
) -> UserRecord:
    user = UserRecord(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name or username,
        email=email,
        status=status,
    )
    session.add(user)
    session.flush()
    session.add(UserPreferenceRecord(user_id=user.id))
    for role_id in role_ids or ["operator"]:
        session.add(UserRoleRecord(user_id=user.id, role_id=role_id))
    session.flush()
    return user


def replace_user_roles(session: Session, user_id: int, role_ids: list[str]) -> None:
    session.execute(delete(UserRoleRecord).where(UserRoleRecord.user_id == user_id))
    for role_id in role_ids:
        session.add(UserRoleRecord(user_id=user_id, role_id=role_id))


def create_session(session: Session, user: UserRecord, *, now: datetime | None = None) -> str:
    resolved_now = now or utc_now()
    token = secrets.token_urlsafe(32)
    session.add(
        SessionRecord(
            user_id=user.id,
            session_hash=session_token_hash(token),
            expires_at=resolved_now + timedelta(days=SESSION_DAYS),
        )
    )
    user.last_login_at = resolved_now
    session.flush()
    return token


def revoke_session(session: Session, token: str | None) -> None:
    if not token:
        return
    record = session.scalar(select(SessionRecord).where(SessionRecord.session_hash == session_token_hash(token)))
    if record is not None and record.revoked_at is None:
        record.revoked_at = utc_now()


def set_session_cookie(response: Response, token: str) -> None:
    secure_cookie = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def principal_payload(principal: Principal) -> dict[str, object]:
    return {
        "user": None
        if not principal.authenticated
        else {
            "id": principal.user_id,
            "username": principal.username,
            "displayName": principal.display_name,
        },
        "roles": principal.roles,
        "permissions": principal.permissions,
        "preferences": principal.preferences,
        "authenticated": principal.authenticated,
    }


def current_principal(request: Request) -> Principal:
    principal = _session_principal(request) or _basic_principal(request) or guest_principal()
    request.state.current_principal = principal
    return principal


def guest_principal() -> Principal:
    return Principal(
        user_id=None,
        username="guest",
        display_name="游客",
        roles=["guest"],
        permissions=PUBLIC_PERMISSIONS.copy(),
        preferences={"theme": "system", "defaultChannel": "ai", "compactMode": False},
        authenticated=False,
        auth_type="guest",
    )


def require_permission(permission: str) -> Callable[[Request], Principal]:
    def dependency(request: Request) -> Principal:
        principal = current_principal(request)
        if permission not in principal.permissions:
            if not principal.authenticated:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"code": "unauthenticated", "message": "请先登录。"},
                    headers={"WWW-Authenticate": "Basic"},
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "forbidden", "message": "当前账号没有访问权限。"},
            )
        return principal

    return dependency


def require_admin(request: Request) -> str:
    return require_permission("ops.dashboard.read")(request).username


def _session_principal(request: Request) -> Principal | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    SessionLocal = getattr(request.app.state, "production_sessionmaker", None)
    if SessionLocal is None:
        return None
    with SessionLocal() as session:
        record = session.scalar(select(SessionRecord).where(SessionRecord.session_hash == session_token_hash(token)))
        if record is None or record.revoked_at is not None or record.expires_at <= utc_now():
            return None
        user = session.get(UserRecord, record.user_id)
        if user is None or user.status != "active":
            return None
        return _principal_for_user(session, user, auth_type="session")


def _basic_principal(request: Request) -> Principal | None:
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception as exc:  # noqa: BLE001 - malformed Basic headers are auth failures.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin credentials") from exc
    settings = Settings()
    username_ok = secrets.compare_digest(username, settings.admin_username)
    password_ok = secrets.compare_digest(password, settings.admin_password)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return Principal(
        user_id=None,
        username=username,
        display_name=username,
        roles=["admin"],
        permissions=ADMIN_PERMISSIONS.copy(),
        preferences={"theme": "system", "defaultChannel": "ai", "compactMode": False},
        authenticated=True,
        auth_type="basic",
    )


def _principal_for_user(session: Session, user: UserRecord, *, auth_type: str) -> Principal:
    roles = list(
        session.scalars(
            select(UserRoleRecord.role_id).where(UserRoleRecord.user_id == user.id).order_by(UserRoleRecord.role_id)
        ).all()
    )
    permissions = sorted(
        set(
            session.scalars(
                select(RolePermissionRecord.permission_id).where(RolePermissionRecord.role_id.in_(roles))
            ).all()
        )
    )
    prefs = session.get(UserPreferenceRecord, user.id)
    return Principal(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        roles=roles,
        permissions=permissions,
        preferences={
            "theme": prefs.theme if prefs else "system",
            "defaultChannel": prefs.default_channel if prefs else "ai",
            "compactMode": prefs.compact_mode if prefs else False,
        },
        authenticated=True,
        auth_type=auth_type,
    )


def _user_has_role(session: Session, user_id: int, role_id: str) -> bool:
    return (
        session.scalar(
            select(UserRoleRecord).where(UserRoleRecord.user_id == user_id).where(UserRoleRecord.role_id == role_id)
        )
        is not None
    )


def audit_log(
    request: Request,
    session: Session,
    *,
    action: str,
    target_type: str,
    target_id: str | int | None = None,
    result: str = "success",
    metadata: dict[str, object] | None = None,
) -> None:
    principal = getattr(request.state, "current_principal", None) or current_principal(request)
    session.add(
        AuditLogRecord(
            actor_user_id=principal.user_id,
            actor_username=principal.username,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            result=result,
            metadata_json=metadata or {},
        )
    )
