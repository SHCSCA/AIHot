import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import type { Credentials } from "../api";

export function LoginPage({
  error,
  onLogin
}: {
  error?: string | null;
  onLogin: (credentials: Credentials) => Promise<void>;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    try {
      await onLogin({ username, password });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel">
        <div className="brand-mark">
          <ShieldCheck size={24} />
        </div>
        <p className="eyebrow">AI 热点情报平台</p>
        <h1>登录运营后台</h1>
        <p>使用后台基础鉴权进入生产运营控制台。</p>
        <label>
          用户名
          <input aria-label="用户名" value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label>
          密码
          <input
            aria-label="密码"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary block" onClick={submit} disabled={submitting}>
          登录
        </button>
      </section>
    </main>
  );
}
