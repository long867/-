"use client";
import { useState } from "react";
import { usePreferences } from "@/hooks/use-preferences";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import type { Token } from "@/types";
export default function Login() {
  const [register, setRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const auth = useAuth();
  const { t } = usePreferences();
  const router = useRouter();
  const mutation = useMutation({
    mutationFn: () =>
      api<Token>(`/auth/${register ? "register" : "login"}`, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    onSuccess: (token) => {
      auth.login(token);
      router.push("/");
    },
  });
  return (
    <main className="small-page">
      <div className="eyebrow">YOUR INTELLIGENCE WORKSPACE</div>
      <h1>
        {register
          ? t("创建账号", "Create account")
          : t("欢迎回来", "Welcome back")}
      </h1>
      <p className="subtitle mb-6">
        {t(
          "保存关注偏好，建立持续的矿产咨询会话。",
          "Save your interests and continue intelligence conversations.",
        )}
      </p>
      <form
        className="form-card"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <label htmlFor="email">{t("电子邮箱", "Email address")}</label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <label htmlFor="password">
          {t("密码（至少 10 个字符）", "Password (at least 10 characters)")}
        </label>
        <input
          id="password"
          type="password"
          autoComplete={register ? "new-password" : "current-password"}
          minLength={10}
          maxLength={128}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        {mutation.isError && (
          <p className="text-red-700 text-sm mt-4" role="alert">
            {mutation.error.message}
          </p>
        )}
        <Button className="w-full mt-6" disabled={mutation.isPending}>
          {mutation.isPending
            ? t("正在验证…", "Verifying…")
            : register
              ? t("注册", "Register")
              : t("登录", "Sign in")}
        </Button>
        <button
          type="button"
          className="text-primary text-sm mt-5"
          onClick={() => {
            setRegister(!register);
            mutation.reset();
          }}
        >
          {register
            ? t("已有账号？登录", "Already have an account? Sign in")
            : t("没有账号？创建账号", "Create an account")}
        </button>
      </form>
    </main>
  );
}
