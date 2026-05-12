# Pind 진행 현황

**Last updated**: 2026-05-13 (초기 작성)

> 세션 시작 시 이 파일을 먼저 읽고, 종료 시 갱신할 것.
> Phase별 체크리스트의 완료 항목은 `- [x]`로 표시하고 commit hash를 옆에 적는다.

---

## 의사결정 로그 (ADR)

| 날짜 | 결정 | 비고 |
|------|------|------|
| 2026-05-13 | 모노레포 (pnpm workspace) | CLAUDE.md hierarchy 활용 |
| 2026-05-13 | 영상 소스: YouTube URL only (yt-dlp) | TikTok/IG는 v2 |
| 2026-05-13 | Supabase + FastAPI 분리 (DB/Auth ↔ AI 파이프라인) | Webhook으로 연결 |
| 2026-05-13 | AI: 하이브리드. A안(Gemini 단일 비디오) 구현, B안 인터페이스 분리 | 정확도 부족 시 B안 전환 |
| 2026-05-13 | 비동기: FastAPI `BackgroundTasks` | 동시 5개↑ 시 RQ 검토 |
| 2026-05-13 | Web: Next.js App Router + 단순화 규칙 (모든 페이지 `'use client'`) | v0 호환 우선 |
| 2026-05-13 | UI: Tailwind + shadcn/ui, v0 워크플로우 | 재사용은 `packages/ui` |
| 2026-05-13 | 상태: Zustand + TanStack Query | |
| 2026-05-13 | 지도: Leaflet + OpenStreetMap (무료) | |
| 2026-05-13 | DB: PostgreSQL 15 + PostGIS 3 (Supabase). SRID 4326 | |
| 2026-05-13 | 인증: Supabase Auth (JWT). FastAPI는 JWKS 검증 | |
| 2026-05-13 | 타입 동기화: Pydantic → OpenAPI → `openapi-typescript` 자동 생성 | 손으로 작성 금지 |

---

## Phase 0: 부트스트랩

- [ ] 0-1. pnpm workspace 모노레포 초기화 (`apps/`, `packages/`)
- [ ] 0-2. 루트 `CLAUDE.md` + 각 디렉토리 `CLAUDE.md` 5개 배치
- [ ] 0-3. `docker-compose.yml` (Postgres+PostGIS) + `make` 타겟
- [ ] 0-4. Supabase CLI 로컬 환경 (`supabase init`, `supabase start`)
- [ ] 0-5. `apps/api` 부트스트랩 (FastAPI + ruff + mypy + pytest + pre-commit)
- [ ] 0-6. `apps/web` 부트스트랩 (`pnpm create next-app` + Tailwind + shadcn/ui init)
- [ ] 0-7. `apps/extension` 부트스트랩 (`pnpm create plasmo`)
- [ ] 0-8. `packages/ui`, `packages/shared-types` 부트스트랩
- [ ] 0-9. `Makefile` (`verify`, `gen:types`, `dev`, `test`, `migrate`)
- [ ] 0-10. pre-commit hook (ruff format, eslint --fix, tsc)

## Phase 1: DB & DTO (Backend)

- [ ] 1-1. `Video`, `Place` SQLAlchemy 모델 (UUID PK, GeoAlchemy2 Geography)
- [ ] 1-1. Alembic 환경 + 초기 마이그레이션 (PostGIS extension 포함)
- [ ] 1-1. GIST 인덱스 + FK 인덱스
- [ ] 1-1. RLS 정책 SQL 작성 (`supabase/migrations/`)
- [ ] 1-2. Pydantic 스키마 (`VideoRead/Create`, `PlaceRead/Create`)
- [ ] 1-2. `GET /api/v1/places` mock 라우터 (더미 JSON)
- [ ] 1-2. `make gen:types` 파이프라인 (openapi.json → `packages/shared-types/api.ts`)
- [ ] 1-2. 단위 테스트: Pydantic 직렬화 (geom ↔ lat/lng 변환)

## Phase 2: Frontend 뼈대

- [ ] 2-1. `packages/shared-types/api.ts` 자동 생성 검증
- [ ] 2-1. `lib/supabase.ts`, `lib/api.ts` wrapper (JWT 자동 첨부)
- [ ] 2-1. Supabase Auth 흐름 (로그인/로그아웃, 세션 복원)
- [ ] 2-2. URL 입력 폼 컴포넌트 (`apps/web/components/VideoForm` → 추후 `packages/ui`)
- [ ] 2-2. 빈 지도 컴포넌트 (Leaflet, `dynamic` import로 SSR 회피)
- [ ] 2-2. 더미 마커 3개 표시 → mock API 호출로 교체

## Phase 3: AI 파이프라인 (Backend, 가장 큰 단계)

- [ ] 3-1. `pipeline/types.py` (PlaceCandidate, Transcript, Frame 등)
- [ ] 3-1. `pipeline/cost_guard.py` (비용 캡)
- [ ] 3-1. `pipeline/download.py` (yt-dlp, 실패 시 도메인 예외)
- [ ] 3-1. `pipeline/audio.py` + `pipeline/frames.py` (ffmpeg, B안용)
- [ ] 3-1. `pipeline/transcribe.py` (faster-whisper, B안용)
- [ ] 3-1. `pipeline/analyze_video.py` (Gemini 단일 비디오 입력, **A안 MVP**)
- [ ] 3-1. 각 모듈 단위 테스트 + `tests/fixtures/sample.mp4`
- [ ] 3-2. `pipeline/resolve.py`: 후보 dedup (sentence-transformers 임베딩 유사도)
- [ ] 3-2. Google Places Text Search 통합 (place_id + geometry)
- [ ] 3-3. `pipeline/orchestrator.py` (전체 흐름 조합)
- [ ] 3-3. `webhooks/video_created.py` + Supabase Database Webhook 설정
- [ ] 3-3. BackgroundTasks로 파이프라인 비동기 실행 + `videos.status` 업데이트
- [ ] 3-3. tenacity 재시도 정책 적용

## Phase 4: Realtime & UI 완성

- [ ] 4-1. `useVideoStatus` 커스텀 훅 (Supabase Realtime 구독)
- [ ] 4-1. 처리 상태 UI (pending → processing → completed/failed)
- [ ] 4-2. 실제 `places` 데이터 마커 표시 (TanStack Query)
- [ ] 4-2. 마커 클릭 시 context 시간 + 영상 임베드 (YouTube iframe + `?t=`)
- [ ] 4-2. 마커 클러스터링 (100개↑)
- [ ] 4-3. Extension popup으로 핵심 컴포넌트 이식 (`packages/ui` 활용)
- [ ] 4-3. content script: 유튜브 페이지 "Pind에 저장" 버튼

## Phase 5: 보안 & 배포

- [ ] 5-1. RLS 정책 모든 테이블 검증 (Supabase Dashboard에서 직접 테스트)
- [ ] 5-1. service_role 키 서버 사이드 전용 격리 재확인
- [ ] 5-2. tenacity 재시도 로직 점검 + 에러 분기 (4xx vs 5xx)
- [ ] 5-2. structlog + Sentry (무료 티어) 셋업
- [ ] 5-2. Dockerfile (FastAPI) + Render or Fly.io 배포
- [ ] 5-2. Vercel에 web 배포 (환경변수 분리)
- [ ] 5-2. Chrome Web Store 제출 (선택, v1.1)

---

## 진행 중

(없음 — Phase 0 시작 전)

## 다음 작업

**Phase 0-1**: 모노레포 디렉토리 구조 + `package.json` workspace 설정부터.

---

## 알려진 이슈 / 검증 필요

- (Phase 3 진행 시) Gemini Vision의 한글 간판 인식률 — 실측 후 confidence threshold 조정
- (Phase 3 진행 시) Place Resolver의 fuzzy match threshold — 실험으로 튜닝
- (Phase 3 진행 시) yt-dlp가 YouTube의 봇 차단에 막힐 가능성 — 우회/캐싱 전략 필요할 수도

## 차후 검토 (v2 후보)

- TikTok/Instagram 영상 지원
- 멀티모달 앙상블(B안) vs A안 정확도 비교 실험 (학회/논문 거리)
- 사용자 영상 직접 업로드
- 다중 사용자 공유 지도
- React Native 모바일 앱
- Edge Function으로 일부 파이프라인 이전 (cold start 허용 영역)
