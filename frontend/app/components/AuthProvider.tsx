"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, Employee } from "../lib/api";

export type CurrentUser = {
  id: number;
  name: string;
  role_name: string | null;
  permissions: string[];
};

type Ctx = {
  user: CurrentUser | null;
  ready: boolean; // localStorage 로드 완료 여부(하이드레이션 깜빡임 방지)
  login: (emp: Employee) => Promise<void>;
  logout: () => void;
  hasPermission: (moduleKey: string) => boolean;
};

const AuthContext = createContext<Ctx | null>(null);
const KEY = "erp_current_user";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setUser(JSON.parse(raw));
    } catch {
      /* ignore */
    }
    setReady(true);
  }, []);

  const login = async (emp: Employee) => {
    let permissions: string[] = [];
    let role_name = emp.role_name ?? null;
    if (emp.role_id) {
      try {
        const roles = await api.roles();
        const r = roles.find((x) => x.id === emp.role_id);
        if (r) {
          permissions = r.permissions;
          role_name = r.name;
        }
      } catch {
        /* 역할 조회 실패 시 권한 없음으로 처리 */
      }
    }
    const cu: CurrentUser = { id: emp.id, name: emp.name, role_name, permissions };
    localStorage.setItem(KEY, JSON.stringify(cu));
    setUser(cu);
  };

  const logout = () => {
    localStorage.removeItem(KEY);
    setUser(null);
  };

  // 대시보드는 항상 허용(로그인 후 랜딩). 나머지는 역할 권한에 따름.
  const hasPermission = (moduleKey: string) =>
    moduleKey === "dashboard" || (user?.permissions.includes(moduleKey) ?? false);

  return (
    <AuthContext.Provider value={{ user, ready, login, logout, hasPermission }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const c = useContext(AuthContext);
  if (!c) throw new Error("useAuth must be used within AuthProvider");
  return c;
}
