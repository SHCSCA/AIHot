import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import type { Credentials } from "../../api";

interface LoginPanelProps {
  error: string | null;
  onLogin: (credentials: Credentials) => Promise<void>;
}

export function LoginPanel({ error, onLogin }: LoginPanelProps) {
  const reducedMotion = useReducedMotion();
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
    <motion.section
      className="public-login-panel dark glass"
      initial={reducedMotion ? false : { opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reducedMotion ? 0 : 0.24, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="login-panel-info">
        <ShieldCheck size={19} />
        <strong>运营后台登录</strong>
        <span>登录后进入信源、事件、日报和策略管理台。</span>
      </div>

      <label>
        <span>管理员账号</span>
        <input
          aria-label="管理员账号"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="用户名"
        />
      </label>

      <label>
        <span>管理员密码</span>
        <input
          aria-label="管理员密码"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="密码"
        />
      </label>

      {error && <p className="error">{error}</p>}

      <button
        className="primary login-btn"
        type="button"
        onClick={submit}
        disabled={submitting}
      >
        {submitting ? "登录中..." : "登录"}
      </button>
    </motion.section>
  );
}
