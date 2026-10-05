"use client";

import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";

import type { MappablePlace } from "@/components/PlacesMap";
import { fetchPlaces, type PlaceRead } from "@/lib/api";

// Leaflet은 window를 바로 만지므로 SSR에서 터진다 (apps/web/CLAUDE.md).
const PlacesMap = dynamic(() => import("@/components/PlacesMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center rounded-md border border-border">
      <p className="text-sm text-muted-foreground">지도 불러오는 중…</p>
    </div>
  ),
});

function hasCoordinates(place: PlaceRead): place is MappablePlace {
  return place.lat != null && place.lng != null;
}

/** 초를 `m:ss` 로. YouTube `?t=` 는 초 단위라 링크에는 원래 값을 쓴다. */
function formatSeconds(total: number): string {
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export default function PlacesPage() {
  const [selected, setSelected] = useState<PlaceRead | null>(null);

  const { data, isPending, error } = useQuery({
    queryKey: ["places"],
    queryFn: () => fetchPlaces({ limit: 200 }),
  });

  // data?.items ?? [] 를 바로 쓰면 매 렌더마다 새 배열이 되어 아래 useMemo 가
  // 무의미해진다 (eslint react-hooks/exhaustive-deps 경고).
  const places = useMemo(() => data?.items ?? [], [data]);
  const mappable = useMemo(() => places.filter(hasCoordinates), [places]);
  const unmapped = useMemo(() => places.filter((p) => !hasCoordinates(p)), [places]);

  return (
    <main className="flex h-screen flex-col gap-4 p-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-bold">장소</h1>
        <a href="/" className="text-sm text-muted-foreground underline">
          홈
        </a>
      </header>

      {error ? (
        <p className="text-sm text-destructive">
          불러오지 못했습니다: {error instanceof Error ? error.message : "알 수 없는 오류"}
        </p>
      ) : null}

      <div className="grid min-h-0 flex-1 gap-4 md:grid-cols-[2fr_1fr]">
        <div className="min-h-[320px]">
          <PlacesMap places={mappable} onSelect={setSelected} />
        </div>

        <aside className="flex min-h-0 flex-col gap-3 overflow-y-auto">
          {isPending ? <p className="text-sm text-muted-foreground">불러오는 중…</p> : null}

          {places.map((place) => (
            <button
              key={place.id}
              type="button"
              onClick={() => setSelected(place)}
              className={`rounded-md border p-3 text-left text-sm ${
                selected?.id === place.id ? "border-primary" : "border-border"
              }`}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium">{place.name}</span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatSeconds(place.context_start_sec)}
                </span>
              </div>
              {place.category ? (
                <p className="text-xs text-muted-foreground">{place.category}</p>
              ) : null}
              {!hasCoordinates(place) ? (
                // 좌표 없는 장소를 숨기지 않는다 — 이름과 영상 구간은 쓸 수 있다.
                <p className="mt-1 text-xs text-muted-foreground">
                  위치를 찾지 못했습니다 (영상 구간만)
                </p>
              ) : null}
            </button>
          ))}

          {!isPending && places.length === 0 ? (
            <p className="text-sm text-muted-foreground">아직 장소가 없습니다.</p>
          ) : null}

          {unmapped.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              {places.length}곳 중 {unmapped.length}곳은 좌표를 찾지 못해 지도에 표시되지 않습니다.
            </p>
          ) : null}
        </aside>
      </div>

      {selected ? (
        <section className="rounded-md border border-border p-3">
          <div className="flex items-baseline justify-between gap-2">
            <h2 className="font-medium">{selected.name}</h2>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="text-xs text-muted-foreground underline"
            >
              닫기
            </button>
          </div>
          <p className="text-xs text-muted-foreground">
            {selected.address ?? "주소 미확인"} · {formatSeconds(selected.context_start_sec)}–
            {formatSeconds(selected.context_end_sec)} · 신뢰도{" "}
            {(selected.confidence * 100).toFixed(0)}%
          </p>
          {selected.raw_extracted_text ? (
            <p className="mt-1 text-xs text-muted-foreground">
              읽은 문자열: {selected.raw_extracted_text}
            </p>
          ) : null}
          {/* 영상 임베드는 Phase 4-2. 지금은 구간 정보만 보여준다. */}
        </section>
      ) : null}
    </main>
  );
}
