import type { components, paths } from "@pind/shared-types";

import { getSupabase } from "./supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// API 호출은 반드시 이 wrapper를 통해서만. fetch 직접 호출 금지.
// JWT는 여기서 자동 첨부한다 (supabase 세션 → Authorization 헤더).

/** OpenAPI에서 생성된 스키마. 손으로 쓴 인터페이스가 아니다. */
export type PlaceRead = components["schemas"]["PlaceRead"];
export type VideoRead = components["schemas"]["VideoRead"];
export type VideoCreate = components["schemas"]["VideoCreate"];
export type PlacePage = components["schemas"]["Page_PlaceRead_"];
export type VideoStatus = components["schemas"]["VideoStatus"];

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await getSupabase().auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** FastAPI는 에러 본문을 `{detail: ...}`로 준다. 422는 detail이 배열이다. */
async function errorMessage(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: string } | undefined;
      if (first?.msg) return first.msg;
    }
  } catch {
    // 본문이 JSON이 아니면 상태 코드만 쓴다.
  }
  return `API ${res.status}: ${res.statusText}`;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(await authHeader()),
    ...((init?.headers as Record<string, string> | undefined) ?? {}),
  };

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (!res.ok) {
    throw new ApiError(res.status, await errorMessage(res));
  }

  return res.json() as Promise<T>;
}

// ── 엔드포인트별 얇은 함수 ──────────────────────────────────────────────────
// 경로 문자열과 응답 타입이 한 곳에서 묶이게 해서, 호출하는 쪽이 경로를 틀리거나
// 타입을 손으로 적을 일이 없게 한다. paths 타입을 참조하므로 OpenAPI에 없는
// 경로를 쓰면 타입 에러가 난다.

type PlacesQuery = NonNullable<paths["/api/v1/places"]["get"]["parameters"]["query"]>;

export async function fetchPlaces(query: PlacesQuery = {}): Promise<PlacePage> {
  const params = new URLSearchParams();
  if (query.video_id) params.set("video_id", query.video_id);
  if (query.limit != null) params.set("limit", String(query.limit));
  if (query.cursor) params.set("cursor", query.cursor);
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return apiFetch<PlacePage>(`/api/v1/places${suffix}`);
}

export async function fetchVideo(videoId: string): Promise<VideoRead> {
  return apiFetch<VideoRead>(`/api/v1/videos/${videoId}`);
}

/**
 * YouTube URL에서 11자 영상 ID를 받아온다.
 *
 * 추출 규칙을 web·extension에 복사하지 않으려고 서버에 둔 엔드포인트다
 * (PROGRESS.md ADR 2026-10-04). `videos` INSERT에 이 값이 필요하다.
 */
export async function resolveVideoUrl(youtubeUrl: string): Promise<VideoCreate> {
  return apiFetch<VideoCreate>("/api/v1/videos/resolve", {
    method: "POST",
    body: JSON.stringify({ youtube_url: youtubeUrl }),
  });
}
