"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useSession } from "@/hooks/useSession";
import { getSupabase } from "@/lib/supabase";

type Mode = "signIn" | "signUp";

export default function LoginPage() {
  const { session, ready, unconfigured } = useSession();
  const [mode, setMode] = useState<Mode>("signIn");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setMessage(null);
    try {
      const auth = getSupabase().auth;
      if (mode === "signIn") {
        const { error: signInError } = await auth.signInWithPassword({ email, password });
        if (signInError) throw signInError;
      } else {
        const { error: signUpError } = await auth.signUp({ email, password });
        if (signUpError) throw signUpError;
        // 이메일 확인이 켜져 있으면 여기서 세션이 생기지 않는다. 사용자가
        // "가입했는데 아무 일도 없다"고 느끼지 않게 명시적으로 알린다.
        setMessage("가입 확인 메일을 보냈습니다. 메일의 링크를 누르면 로그인됩니다.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "로그인에 실패했습니다");
    } finally {
      setPending(false);
    }
  }

  async function signOut() {
    await getSupabase().auth.signOut();
  }

  if (unconfigured) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-3 p-8">
        <h1 className="text-2xl font-bold">설정이 필요합니다</h1>
        <p className="text-sm text-muted-foreground">
          <code>apps/web/.env.local</code> 에 <code>NEXT_PUBLIC_SUPABASE_URL</code> 과{" "}
          <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> 를 넣어 주세요.{" "}
          <code>.env.example</code> 을 복사하면 됩니다.
        </p>
      </main>
    );
  }

  if (!ready) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md items-center justify-center p-8">
        <p className="text-sm text-muted-foreground">세션 확인 중…</p>
      </main>
    );
  }

  if (session) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 p-8">
        <h1 className="text-2xl font-bold">로그인됨</h1>
        <p className="text-sm text-muted-foreground">{session.user.email}</p>
        <div className="flex gap-2">
          <Button asChild variant="secondary">
            <a href="/">홈으로</a>
          </Button>
          <Button variant="outline" onClick={signOut}>
            로그아웃
          </Button>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 p-8">
      <div>
        <h1 className="text-2xl font-bold">{mode === "signIn" ? "로그인" : "회원가입"}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          영상을 등록하려면 로그인이 필요합니다.
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          이메일
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          비밀번호
          <input
            type="password"
            required
            minLength={6}
            autoComplete={mode === "signIn" ? "current-password" : "new-password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
          />
        </label>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}

        <Button type="submit" disabled={pending}>
          {pending ? "처리 중…" : mode === "signIn" ? "로그인" : "가입"}
        </Button>
      </form>

      <button
        type="button"
        onClick={() => {
          setMode(mode === "signIn" ? "signUp" : "signIn");
          setError(null);
          setMessage(null);
        }}
        className="text-sm text-muted-foreground underline"
      >
        {mode === "signIn" ? "계정이 없으신가요? 가입하기" : "이미 계정이 있으신가요? 로그인"}
      </button>
    </main>
  );
}
