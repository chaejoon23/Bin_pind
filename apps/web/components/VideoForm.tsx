"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError, resolveVideoUrl } from "@/lib/api";
import { getSupabase } from "@/lib/supabase";

type Props = {
  /** 로그인한 사용자 id. 없으면 폼이 잠긴다. */
  userId: string | null;
  onSubmitted?: (videoId: string) => void;
};

export function VideoForm({ userId, onSubmitted }: Props) {
  const [url, setUrl] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!userId) return;
    setPending(true);
    setError(null);
    setNotice(null);

    try {
      // 1) URL → 영상 ID. 규칙은 서버에 한 곳만 둔다.
      const resolved = await resolveVideoUrl(url);

      // 2) videos INSERT. 이 INSERT가 Database Webhook으로 파이프라인을 깨운다
      //    (CLAUDE.md 연결 흐름). 그래서 여기서 FastAPI를 직접 부르지 않는다.
      //    컬럼 권한상 클라이언트가 넣을 수 있는 건 이 세 개뿐이다.
      const { data, error: insertError } = await getSupabase()
        .from("videos")
        .insert({
          user_id: userId,
          youtube_url: String(resolved.youtube_url),
          youtube_id: resolved.youtube_id,
        })
        .select("id")
        .single();

      if (insertError) {
        // UNIQUE (user_id, youtube_id) 위반 = 이미 넣은 영상. 에러가 아니라 안내다.
        if (insertError.code === "23505") {
          setNotice("이미 등록한 영상입니다. 목록에서 확인하세요.");
          return;
        }
        throw new Error(insertError.message);
      }

      setUrl("");
      setNotice("등록했습니다. 분석이 끝나면 지도에 표시됩니다.");
      onSubmitted?.(data.id as string);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 422) {
        setError("YouTube 영상 URL이 아닙니다. 주소를 다시 확인해 주세요.");
      } else {
        setError(cause instanceof Error ? cause.message : "등록에 실패했습니다");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex w-full flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        YouTube 영상 주소
        <input
          type="url"
          required
          placeholder="https://www.youtube.com/watch?v=..."
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          disabled={!userId || pending}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm disabled:opacity-50"
        />
      </label>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {notice ? <p className="text-sm text-muted-foreground">{notice}</p> : null}

      <Button type="submit" disabled={!userId || pending || url.trim().length === 0}>
        {pending ? "등록 중…" : "장소 찾기"}
      </Button>

      {!userId ? (
        <p className="text-sm text-muted-foreground">
          <a href="/login" className="underline">
            로그인
          </a>{" "}
          후 등록할 수 있습니다.
        </p>
      ) : null}
    </form>
  );
}
