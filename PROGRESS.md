# Pind 진행 현황

**Last updated**: 2026-09-14

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
| 2026-05-20 | DB 연결: Docker 없이 Supabase Cloud Session Pooler 직접 사용 | IPv6 직접 연결 대신 Session Pooler(:5432) — Alembic/FastAPI 모두 동일 |
| 2026-05-20 | Gemini 모델: `gemini-3.1-flash-lite` 고정 | |
| 2026-06-11 | web 스택: **Next.js 14 + React 18 + Tailwind v3 + shadcn 2.3.0** 고정 | 최신 shadcn(v4)은 Tailwind v4+base-ui 전제라 우리 스택과 충돌 → 2.x(Radix) 사용. 토큰은 tailwind.config.ts(HSL) |
| 2026-06-11 | shadcn 토큰 oklch→HSL 트리플릿 교체 | shadcn 2.3.0이 oklch를 쓰는데 v3 config는 `hsl(var(--x))`로 감싸 무효화됨 → 정통 zinc HSL 팔레트로 globals.css 재작성 |
| 2026-06-11 | RootLayout만 Server Component 예외 허용 | `metadata` export 때문. 데이터 패칭/Server Action 없음. 페이지는 모두 `'use client'` |
| 2026-06-11 | Extension: Plasmo 0.90.5 + React 18 | create-plasmo가 example template을 잡아 package.json 수동 정정. Tailwind는 후속 |
| 2026-06-11 | shared-types `api.ts` 추적(gitignore 해제) | 생성 타입이지만 커밋 → 클론 직후 typecheck 보장. gen-types가 덮어씀 |
| 2026-06-11 | ui lint: eslint 9 flat config + typescript-eslint | next/* import 금지 규칙. 컴포넌트 생기면 eslint-plugin-react 추가 |
| 2026-09-14 | **비전 프론트엔드를 Phase 3보다 먼저 구현** | B안(프레임 기반)의 입력단. A안(Gemini 단일 비디오)과 독립이라 선행 가능하고, 프레임 수 감축이 비용 캡 설계의 입력값이 된다 |
| 2026-09-14 | **저조도 복원을 화질 게이트보다 앞에 배치** | 게이트 먼저 두면 실내 저조도 프레임이 전부 `underexposed` 탈락 → 실내 장소가 결과에서 사라짐(검증 영상에서 전시장 간판 유실 확인). 게이트의 역할을 "품질 낮은 프레임 제거"에서 "복원해도 못 읽는 프레임 제거"로 재정의 |
| 2026-09-14 | 디노이징 판정을 **감마 후** σ 기준으로 | 어두운 화소는 노이즈 진폭도 눌려 원본 σ가 과소평가됨(1.26 → 감마 후 3.22 → CLAHE 후 5.93). 강도도 σ 비례(h≈2.5σ), 위치는 CLAHE 앞 |
| 2026-09-14 | 장면 임베더는 `Embedder` 프로토콜로 교체 가능하게 | 기본 pHash+HSV(의존성 0), 옵션 DINOv3 ViT-S/16(`[vision-embed]` extra). 컷 전환은 고전 방식으로 충분하고 서버 비용이 싸다. 재방문 판정 비교 실험은 미실시 |
| 2026-09-14 | 선명도 임계는 영상별 **상대** 기준(90퍼센타일 정규화 + 하위 N% 컷) | 절대 임계값은 촬영 기기·비트레이트에 따라 자리가 크게 달라져 재사용 불가 |
| 2026-09-14 | 벤치마크 입력은 **합성 영상** | 실제 YouTube 영상은 저작권·재현성 문제. `benchmarks/make_sample_video.py`로 누구나 같은 수치 재현. 단, 실영상 성능 보장 아님 → 실영상 검증은 별도 과제 |

---

## Phase 0: 부트스트랩

- [x] 0-1. pnpm workspace 모노레포 초기화 (`apps/`, `packages/`) — package.json, pnpm-workspace.yaml, packages/{shared-types,ui}, tsconfig.json, .gitignore
- [x] 0-2. 루트 `CLAUDE.md` + 각 디렉토리 `CLAUDE.md` 5개 배치 — 완비 확인
- [x] 0-3. `docker-compose.yml` + `Makefile` 작성 완료 — **Docker 불필요 확정**: DB는 Supabase Cloud 직접 연결(Session Pooler :5432)로 대체. docker-compose는 Phase 5 배포 테스트용으로 보존
- [x] 0-4. Supabase CLI 설정 완료 — `supabase init` + `supabase link` (bin_pind / fqltlhaqmfmnerriellm, Seoul), RLS 마이그레이션 파일 작성 (`supabase/migrations/20260520000001_enable_rls_videos_places.sql`)
- [x] 0-5. `apps/api` 부트스트랩 완료
  - pyproject.toml (fastapi, sqlalchemy, alembic, asyncpg, geoalchemy2, google-genai, faster-whisper, yt-dlp, sentence-transformers 등 전체 패키지 설치)
  - `app/` 뼈대: main.py, settings.py, exceptions.py, models/base.py, deps.py
  - `alembic/` 환경 구성 (env.py — ConfigParser `%` 이슈 우회, Session Pooler 직접 연결)
  - pyrightconfig.json (.venv 인식), .pre-commit-config.yaml, .env.example
  - FastAPI `/health` 기동 확인, `alembic current` DB 연결 확인
- [x] 0-6. `apps/web` 부트스트랩 완료
  - Next.js 14.2.35 + React 18 + Tailwind v3.4 (create-next-app, App Router, no src, alias `@/*`)
  - shadcn/ui `2.3.0` init (new-york/zinc) + `components/ui/button.tsx`, `lib/utils.ts`
  - globals.css 토큰 oklch→HSL 보정, tailwind.config `destructive.foreground` 추가
  - 단순화 규칙 적용: `app/page.tsx` `'use client'`, RootLayout만 metadata용 server shell + `app/providers.tsx`(client) 마운트
  - `lib/{supabase,api,query-client}.ts` 스켈레톤 (JWT 자동 첨부 wrapper 구조)
  - 워크스페이스 deps 연결: `@pind/shared-types`, `@pind/ui` / 런타임 deps: supabase-js, TanStack Query, zustand, leaflet
  - `components/`, `hooks/`, `stores/` 디렉토리 배치
  - `pnpm verify`(lint+typecheck) + `next build` 전체 통과
  - ⚠️ 임시조치: `packages/shared-types/src/api.ts` placeholder stub(1-2에서 gen:types가 덮어씀), `@pind/ui` lint는 no-op placeholder(0-8에서 eslint 설정)
- [x] 0-7. `apps/extension` 부트스트랩 완료
  - Plasmo 0.90.5 + React 18 (popup.tsx 진입점, tsconfig는 `plasmo/templates/tsconfig.base` 확장, alias `~*`)
  - package.json 정정: `@pind/extension` (create-plasmo가 example template "with-popup"+`plasmo: workspace:*`를 잡아 수동 교체)
  - `lib/{storage,supabase,api}.ts` 스켈레톤: `@plasmohq/storage` 래퍼, chrome.storage 어댑터 supabase 클라이언트(persistSession), web과 동일 api wrapper
  - `components/`, `hooks/`, `stores/`, `contents/` 디렉토리 배치
  - env: `PLASMO_PUBLIC_*` (`.env.example` 커밋 / `.env.local` gitignore)
  - manifest host_permissions: localhost:8000, Supabase. permissions: storage
  - 인입 .github/workflows(Chrome Web Store submit) 제거 — 모노레포 하위라 미작동, 배포는 Phase 5-2 루트 구성
  - `.gitignore`에 `*.tsbuildinfo` 추가, `pnpm verify`(typecheck) 통과
  - ⚠️ `plasmo dev/build`는 네이티브 빌드 스크립트(@swc/core, esbuild, lmdb, sharp) 필요 → 최초 1회 `pnpm approve-builds` 후 사용. Tailwind는 후속 도입(현재 popup 인라인 style)
- [x] 0-8. `packages/ui`, `packages/shared-types` 부트스트랩 완료
  - **shared-types**: `src/api.ts` gitignore 해제 → 생성 타입을 추적 산출물로 커밋(클론 직후 typecheck 보장). `make gen-types`(openapi-typescript)가 덮어씀. placeholder seed 커밋(Phase 1-2에서 실제 타입으로 교체)
  - **ui**: 정식 eslint 도입 — flat config(`eslint.config.mjs`, eslint 9 + typescript-eslint 8), no-op placeholder lint 교체(`eslint src`). `next/*` import 금지 규칙(`no-restricted-imports`) 추가 + 동작 검증 완료
  - eslint-plugin-react는 첫 컴포넌트 승격 시(Phase 4-3) 추가 예정 (현재 컴포넌트 없음, YAGNI)
  - `pnpm verify` 전체 통과 (web·extension·ui·shared-types lint+typecheck)
- [x] 0-9. `Makefile` 정비 완료
  - `make verify` = `verify-api`(ruff/format/mypy) + `verify-js`(루트 recursive: web·extension·ui·shared-types) — 기존엔 api+web만 커버하던 걸 전체 모노레포로 정합
  - api 타깃을 `.venv/bin/` 명시 → venv 수동 활성화 없이도 `make verify`/`dev`/`migrate`/`test` 동작
  - `make dev`에서 docker `db-up` 의존 제거(DB는 Supabase Cloud), Web+API 동시 실행
  - 누락됐던 `test-web` 타깃 추가(placeholder, Phase 2+에서 실제 테스트)
  - `make verify` 녹색화 과정에서 드러난 기존 `alembic/env.py` import 정렬(ruff I001) 수정
  - `make verify` 전체 통과 검증 완료
- [x] 0-10. pre-commit hook 완료
  - `.pre-commit-config.yaml` 재설계: isolated env(버전 핀고정) → `repo: local` + `language: system`으로 전환 → `make verify`와 **동일 버전**(apps/api/.venv ruff/mypy, pnpm) 호출, 버전 스큐 제거
  - 훅: 위생(merge-conflict/yaml/EOF/trailing) + api(ruff --fix, ruff-format, mypy) + js(eslint·next lint, tsc typecheck)
  - `pre-commit install` 완료(.git/hooks/pre-commit), `run --all-files` 전부 통과 (EOF: components.json 개행 보정)

> **Phase 0 부트스트랩 전체 완료 (0-1 ~ 0-10) ✅**

## 비전 프론트엔드 (Phase 3 선행 구현)

`apps/api/app/pipeline/vision/` — VLM 호출 앞단의 프레임 선별·복원. 설계 근거와 측정값은
[docs/vision-frontend.md](docs/vision-frontend.md).

- [x] `vision/types.py` — Pydantic 타입 (QualityMetrics, FrameStats, ShotSegment, Keyframe, VisionFrontendConfig, KeyframeSelection)
- [x] `vision/decode.py` — ffmpeg 균일 샘플링 + 긴 변 리사이즈, ffprobe 길이 측정
- [x] `vision/quality.py` — 무참조 화질 지표 (Laplacian var, Tenengrad, Immerkær σ, Hasler colorfulness, 포화율/RMS) + `readability_score`
- [x] `vision/textness.py` — MSER 기반 간판 문자 saliency (한글 세로쓰기 종횡비 포함)
- [x] `vision/isp.py` — 미니 ISP (Shades-of-Gray WB → 적응 감마 → 조건부 NL-Means → LAB CLAHE → 조건부 언샤프) + `rescue_exposure` 경량 경로
- [x] `vision/embed.py` — `Embedder` 프로토콜 / pHash+HSV 기본 / DINOv3 옵션 / `build_embedder("auto")` 폴백
- [x] `vision/dedup.py` — 인접 유사도 샷 분할 + 전역 중복 샷 제거
- [x] `vision/select.py` — 오케스트레이터 `select_keyframes`
- [x] `benchmarks/bench_keyframes.py` + `make_sample_video.py` — 단계별 감축 표 · 토큰 절감 · 전후 비교 이미지 · 프레임별 CSV
- [x] 단위/엔드투엔드 테스트 63개, ruff(ANN) + mypy strict 통과
- [ ] **실영상 검증** — 실제 브이로그 10편으로 감축률뿐 아니라 **장소 추출 재현율** 측정
- [ ] DINOv3 vs pHash 재방문 판정 비교 실험
- [ ] 문자 점수 정규화 상수 실사 분포로 재튜닝
- [ ] `analyze_vision`(Gemini Vision) 연결 — Phase 3-1에서

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

## Phase 3: AI 파이프라인 (Backend, 가장 큰 단계) bkit이 만든 문서 추가

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

**Phase 0 완료** (0-1 ~ 0-10). **비전 프론트엔드 구현 완료** — 합성 영상 기준 프레임 90.6% 감축,
저조도 프레임 구제로 실내 장소 유실 해결. 실영상 검증은 미완.

## 다음 작업

1. **Phase 1-1**: `Video`, `Place` SQLAlchemy 모델(UUID PK, GeoAlchemy2 Geography) + Alembic 초기 마이그레이션(PostGIS extension) + GIST/FK 인덱스 → `alembic upgrade head` → RLS 마이그레이션 `supabase db push`. (복잡 feature → `/pdca plan` 고려)
2. **비전 프론트엔드 실영상 검증** — 브이로그 10편, 정답 장소 목록을 직접 만들고 재현율 측정. 프레임을 줄여서 놓친 장소가 있는지가 진짜 지표

---

## 알려진 이슈 / 검증 필요

- (Phase 3 진행 시) Gemini Vision의 한글 간판 인식률 — 실측 후 confidence threshold 조정
- (Phase 3 진행 시) Place Resolver의 fuzzy match threshold — 실험으로 튜닝
- (Phase 3 진행 시) yt-dlp가 YouTube의 봇 차단에 막힐 가능성 — 우회/캐싱 전략 필요할 수도
- 비전 프론트엔드 수치는 **합성 영상 기준**. 실영상 성능은 미검증
- 샷 분할 임계 0.88은 경험값. 영상 종류(도심 워킹 / 실내 카페 / 야외)별 적정값이 다를 가능성
- 문자 saliency 정규화 상수가 합성 영상에서 쉽게 포화 — 실사 분포로 재튜닝 필요
- DINOv3 라이선스가 Apache/MIT가 아님 → 상용 배포 전 조건 확인 필요
- 배포 이미지에 ffmpeg 포함 필요 (비전 프론트엔드가 외부 프로세스로 호출)

## 차후 검토 (v2 후보)

- TikTok/Instagram 영상 지원
- 멀티모달 앙상블(B안) vs A안 정확도 비교 실험 (학회/논문 거리)
- 사용자 영상 직접 업로드
- 다중 사용자 공유 지도
- React Native 모바일 앱
- Edge Function으로 일부 파이프라인 이전 (cold start 허용 영역)
