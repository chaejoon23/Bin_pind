import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// 브라우저용 Supabase 클라이언트. anon 키만 사용 (service_role 노출 금지).
// auth 세션은 supabase-js가 자동 관리하므로 localStorage 직접 접근 금지.
//
// 지연 생성인 이유: 모듈 최상단에서 환경변수를 검사하고 throw하면 `next build`가
// 깨진다. 모든 페이지에 'use client'를 박아도 Next는 빌드 때 한 번 프리렌더를
// 돌리고, 그 시점엔 .env.local이 없는 CI 환경일 수 있다. 실제로 호출될 때
// 터지게 해두면 빌드는 통과하고 런타임에만 분명한 메시지가 뜬다.
let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (client) return client;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    throw new Error(
      "NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY 가 없습니다 (.env.local 확인)",
    );
  }

  client = createClient(url, anonKey);
  return client;
}

/** 환경변수가 갖춰졌는지. 로그인 UI에서 설정 안내를 띄울 때 쓴다. */
export function isSupabaseConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  );
}
