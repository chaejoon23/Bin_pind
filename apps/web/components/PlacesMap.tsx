"use client";

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useRef } from "react";

import type { PlaceRead } from "@/lib/api";

/** 좌표가 있는 장소만. 지오코딩 실패 장소는 지도에 꽂을 수 없다. */
export type MappablePlace = PlaceRead & { lat: number; lng: number };

type Props = {
  places: MappablePlace[];
  onSelect?: (place: MappablePlace) => void;
  /** 좌표가 하나도 없을 때 보여줄 중심. 기본값은 서울 시청. */
  fallbackCenter?: { lat: number; lng: number };
};

const SEOUL = { lat: 37.5665, lng: 126.978 };

export default function PlacesMap({ places, onSelect, fallbackCenter = SEOUL }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);

  // 지도 인스턴스는 한 번만 만든다. React의 StrictMode는 effect를 두 번 돌리므로
  // cleanup에서 remove()하지 않으면 "Map container is already initialized"가 난다.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, { center: [SEOUL.lat, SEOUL.lng], zoom: 12 });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map);

    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    for (const place of places) {
      // circleMarker를 쓴다 — Leaflet 기본 마커는 아이콘 PNG를 상대 경로로 찾아서
      // 번들러를 거치면 깨진다(유명한 broken-marker-icon 문제). 이미지 자산이
      // 아예 필요 없는 벡터 마커가 번들러와 무관하게 동작한다.
      const marker = L.circleMarker([place.lat, place.lng], {
        radius: 8,
        weight: 2,
        color: "#1d4ed8",
        fillColor: "#3b82f6",
        // 신뢰도를 투명도로. 낮은 신뢰도 핀을 숨기지 않고 약하게 보여준다.
        fillOpacity: 0.35 + 0.55 * place.confidence,
      });
      marker.bindTooltip(place.name, { direction: "top" });
      marker.on("click", () => onSelect?.(place));
      marker.addTo(layer);
    }

    if (places.length > 0) {
      const bounds = L.latLngBounds(places.map((p) => [p.lat, p.lng] as [number, number]));
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
    } else {
      map.setView([fallbackCenter.lat, fallbackCenter.lng], 12);
    }
  }, [places, onSelect, fallbackCenter]);

  return <div ref={containerRef} className="h-full w-full rounded-md" />;
}
