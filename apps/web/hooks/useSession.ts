"use client";

import type { Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";

import { getSupabase, isSupabaseConfigured } from "@/lib/supabase";

export type SessionState = {
  session: Session | null;
  /** 세션 복원이 끝났는지. false인 동안 "로그인 안 됨"으로 판단하면 깜빡인다. */
  ready: boolean;
  /** 환경변수가 없어 Supabase를 아예 못 쓰는 상태. */
  unconfigured: boolean;
};

/**
 * Supabase 세션을 구독한다.
 *
 * `getSession()`만 쓰면 다른 탭에서 로그아웃했을 때 이 탭이 모른다.
 * `onAuthStateChange`까지 붙여야 토큰 갱신·로그아웃이 반영된다.
 */
export function useSession(): SessionState {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const unconfigured = !isSupabaseConfigured();

  useEffect(() => {
    if (unconfigured) {
      setReady(true);
      return;
    }
    const client = getSupabase();
    let active = true;

    client.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      setReady(true);
    });

    const { data: subscription } = client.auth.onAuthStateChange((_event, next) => {
      setSession(next);
      setReady(true);
    });

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, [unconfigured]);

  return { session, ready, unconfigured };
}
