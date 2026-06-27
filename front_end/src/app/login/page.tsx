"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { LogIn, UserPlus } from "lucide-react";

import { useAuth } from "@/hooks/useAuth";
import { classNames } from "@/utils/format";

const loginSchema = z.object({
  email: z.string().email("Invalid email"),
  password: z.string().min(8, "Min 8 characters"),
});

const registerSchema = z.object({
  username: z.string().min(3, "Min 3 characters"),
  email: z.string().email("Invalid email"),
  full_name: z.string().optional(),
  password: z.string().min(8, "Min 8 characters"),
  confirm_password: z.string(),
}).refine((d) => d.password === d.confirm_password, {
  message: "Passwords do not match",
  path: ["confirm_password"],
});

type LoginForm = z.infer<typeof loginSchema>;
type RegisterForm = z.infer<typeof registerSchema>;

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const { login, register } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [error, setError] = useState<string | null>(null);

  const loginForm = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const registerForm = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      username: "",
      email: "",
      full_name: "",
      password: "",
      confirm_password: "",
    },
  });

  const onLogin = async (values: LoginForm) => {
    setError(null);
    try {
      const me = await login(values);
      const roles = me?.roles ?? [];
      if (roles.includes("analyst") || roles.includes("scientist") || roles.includes("admin")) {
        router.replace("/dashboard");
      } else {
        router.replace("/games");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    }
  };

  const onRegister = async (values: RegisterForm) => {
    setError(null);
    try {
      await register(values);
      router.replace("/games");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Registration failed");
    }
  };

  return (
    <div className="mx-auto mt-16 max-w-md rounded-md border border-white/10 bg-bg-soft p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">
          {mode === "login" ? "Sign in" : "Create account"}
        </h1>
        <button
          type="button"
          onClick={() => {
            setError(null);
            setMode((m) => (m === "login" ? "register" : "login"));
          }}
          className="text-xs text-accent hover:underline"
        >
          {mode === "login" ? "Need an account?" : "Have an account? Sign in"}
        </button>
      </div>

      {error && (
        <div className="mb-3 rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
          {error}
        </div>
      )}

      {mode === "login" ? (
        <form onSubmit={loginForm.handleSubmit(onLogin)} className="space-y-3">
          <Field label="Email" error={loginForm.formState.errors.email?.message}>
            <input
              type="email"
              autoComplete="email"
              {...loginForm.register("email")}
              className={inputCls}
            />
          </Field>
          <Field label="Password" error={loginForm.formState.errors.password?.message}>
            <input
              type="password"
              autoComplete="current-password"
              {...loginForm.register("password")}
              className={inputCls}
            />
          </Field>
          <button
            type="submit"
            disabled={loginForm.formState.isSubmitting}
            className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-accent/40 bg-accent/20 px-3 py-2 text-sm text-accent hover:bg-accent/30 disabled:opacity-50"
          >
            <LogIn className="h-4 w-4" />
            Sign in
          </button>
        </form>
      ) : (
        <form onSubmit={registerForm.handleSubmit(onRegister)} className="space-y-3">
          <Field label="Username" error={registerForm.formState.errors.username?.message}>
            <input type="text" autoComplete="username" {...registerForm.register("username")} className={inputCls} />
          </Field>
          <Field label="Email" error={registerForm.formState.errors.email?.message}>
            <input type="email" autoComplete="email" {...registerForm.register("email")} className={inputCls} />
          </Field>
          <Field label="Full name (optional)" error={registerForm.formState.errors.full_name?.message}>
            <input type="text" autoComplete="name" {...registerForm.register("full_name")} className={inputCls} />
          </Field>
          <Field label="Password" error={registerForm.formState.errors.password?.message}>
            <input type="password" autoComplete="new-password" {...registerForm.register("password")} className={inputCls} />
          </Field>
          <Field label="Confirm password" error={registerForm.formState.errors.confirm_password?.message}>
            <input type="password" autoComplete="new-password" {...registerForm.register("confirm_password")} className={inputCls} />
          </Field>
          <button
            type="submit"
            disabled={registerForm.formState.isSubmitting}
            className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-accent/40 bg-accent/20 px-3 py-2 text-sm text-accent hover:bg-accent/30 disabled:opacity-50"
          >
            <UserPlus className="h-4 w-4" />
            Create account
          </button>
        </form>
      )}
    </div>
  );
}

const inputCls =
  "w-full rounded-md border border-white/10 bg-bg px-3 py-2 text-sm focus:border-accent focus:outline-none";

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-[11px] uppercase tracking-wide text-white/50">{label}</span>
      <div className="mt-1">{children}</div>
      {error && (
        <span className={classNames("mt-1 block text-[11px] text-rose-300")}>
          {error}
        </span>
      )}
    </label>
  );
}
