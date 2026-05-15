import { useState } from "react";
import type { AdminApi } from "../api";
import { useAsyncData } from "../hooks";
import type { AuditLog, Permission, Role, UserAccount } from "../types";
import { formatDateTime } from "../utils";
import { Section, TableWrap } from "../components/Section";
import { auditActionLabel, auditResultLabel, auditTargetLabel, permissionLabel, roleLabel } from "../labels";

export function UsersView({ api }: { api: AdminApi }) {
  const { data: users, error, loading, reload } = useAsyncData<UserAccount[]>(() => api.listUsers(), []);
  const [form, setForm] = useState({ username: "", password: "", displayName: "", email: "", roleIds: ["operator"] });
  async function create() {
    await api.createUser({
      username: form.username,
      password: form.password,
      displayName: form.displayName || form.username,
      email: form.email || undefined,
      roleIds: form.roleIds
    });
    setForm({ username: "", password: "", displayName: "", email: "", roleIds: ["operator"] });
    reload();
  }
  return (
    <div className="view-stack">
      <Section title="用户管理" description="创建、停用和分配运营账号。" error={error} action={<button onClick={reload}>{loading ? "刷新中..." : "刷新"}</button>}>
        <div className="admin-filter-panel access-form">
          <input aria-label="用户名" placeholder="用户名" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} />
          <input aria-label="显示名" placeholder="显示名" value={form.displayName} onChange={(event) => setForm({ ...form, displayName: event.target.value })} />
          <input aria-label="邮箱" placeholder="邮箱" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
          <input aria-label="初始密码" placeholder="初始密码" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
          <select aria-label="角色" value={form.roleIds[0]} onChange={(event) => setForm({ ...form, roleIds: [event.target.value] })}>
            <option value="operator">运营</option>
            <option value="admin">管理员</option>
          </select>
          <button className="primary" onClick={create} disabled={!form.username || !form.password}>新增用户</button>
        </div>
        <TableWrap>
          <table>
            <thead><tr><th>用户</th><th>角色</th><th>状态</th><th>最近登录</th></tr></thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td><strong>{user.displayName}</strong><span>{user.username} · {user.email || "未填写邮箱"}</span></td>
                  <td>{user.roles.map(roleLabel).join("、")}</td>
                  <td><span className={user.status === "active" ? "status-good" : "status-warn"}>{user.status === "active" ? "启用" : "停用"}</span></td>
                  <td>{formatDateTime(user.lastLoginAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}

export function RolesView({ api }: { api: AdminApi }) {
  const { data, error, loading, reload } = useAsyncData<{ roles: Role[]; permissions: Permission[] }>(() => api.listRoles(), { roles: [], permissions: [] });
  const permissionNames = new Map(data.permissions.map((permission) => [permission.id, permission.name]));
  return (
    <div className="view-stack">
      <Section title="角色权限" description="首版固定游客、运营和管理员三类角色，按权限矩阵展示能力。" error={error} action={<button onClick={reload}>{loading ? "刷新中..." : "刷新"}</button>}>
        <div className="role-matrix">
          {data.roles.map((role) => (
            <article key={role.id}>
              <div><strong>{role.name && role.name !== role.id ? role.name : roleLabel(role.id)}</strong><span>{role.description}</span></div>
              <div className="permission-chips">
                {role.permissions.map((permission) => <span key={permission}>{permissionNames.get(permission) ?? permissionLabel(permission)}</span>)}
              </div>
            </article>
          ))}
        </div>
      </Section>
    </div>
  );
}

export function AuditLogsView({ api }: { api: AdminApi }) {
  const { data: logs, error, loading, reload } = useAsyncData<AuditLog[]>(() => api.listAuditLogs({ take: 100 }), []);
  return (
    <div className="view-stack">
      <Section title="操作审计" description="记录用户对生产对象的关键写操作。" error={error} action={<button onClick={reload}>{loading ? "刷新中..." : "刷新"}</button>}>
        <TableWrap>
          <table>
            <thead><tr><th>时间</th><th>用户</th><th>动作</th><th>对象</th><th>结果</th></tr></thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td>{formatDateTime(log.createdAt)}</td>
                  <td>{log.actorUsername}</td>
                  <td>{auditActionLabel(log.action)}</td>
                  <td>{auditTargetLabel(log.targetType, log.targetId)}</td>
                  <td>{auditResultLabel(log.result)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Section>
    </div>
  );
}
