"use client";

import { Button } from "@/components/ui/button";
import { VideoForm } from "@/components/VideoForm";
import { useSession } from "@/hooks/useSession";
import { getSupabase } from "@/lib/supabase";

export default function HomePage() {
  const { session, ready, unconfigured } = useSession();

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-8 p-8">
      <div>
        <h1 className="text-3xl font-bold">Pind</h1>
        <p className="mt-1 text-muted-foreground">
          YouTube 브이로그를 넣으면 창작자가 다녀간 장소를 지도에 꽂아 줍니다.
        </p>
      </div>

      {unconfigured ? (
        <p className="text-sm text-muted-foreground">
          <code>apps/web/.env.local</code> 설정이 필요합니다 (<code>.env.example</code> 참고).
        </p>
      ) : (
        <VideoForm userId={ready ? (session?.user.id ?? null) : null} />
      )}

      <div className="flex items-center gap-2 text-sm">
        <Button asChild variant="secondary">
          <a href="/places">장소 보기</a>
        </Button>
        {ready && session ? (
          <button
            type="button"
            onClick={() => void getSupabase().auth.signOut()}
            className="text-muted-foreground underline"
          >
            로그아웃 ({session.user.email})
          </button>
        ) : (
          <a href="/login" className="text-muted-foreground underline">
            로그인
          </a>
        )}
      </div>
    </main>
  );
}
