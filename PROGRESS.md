# Pind 진행 현황

**Last updated**: 2026-10-05

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
| 2026-09-15 | **유사도 임계를 임베더별 권장값으로** (perceptual 0.88/0.95, dinov3 0.97/0.97) | 코사인 스케일이 임베더마다 다름(다른 장면 쌍 최대: pHash 0.247 vs DINOv3 0.941). pHash용 0.88을 DINOv3에 쓰면 감축률은 94.3%로 올랐지만 장소 2곳 유실. 과분할 쪽 오차를 택함 |
| 2026-10-05 | **Phase 3 는 A안·B안 둘 다 만들어 같은 영상에서 비교** | A안(Gemini 영상 직접 입력)만 만들면 `pipeline/vision/` 전체가 실행 경로에서 빠진다. 인터페이스만 갈라놓고 동일 영상에서 장소 재현율·비용을 비교하면, 이미 만든 장소 보존률 하네스가 그대로 평가 도구가 되고 "어떤 설계가 우월한가"를 상한·비용까지 묶어 답할 수 있다 |
| 2026-10-05 | **supabase-js 클라이언트를 지연 생성으로** | 모듈 최상단에서 환경변수를 검사해 throw 하면 `next build` 가 깨진다. 모든 페이지에 `'use client'` 를 박아도 Next 는 빌드 때 프리렌더를 한 번 돌린다. 호출 시점에 터지게 바꿔 환경변수 없이도 빌드가 통과(확인함) |
| 2026-10-05 | **지도 마커는 Leaflet 기본 아이콘 대신 `circleMarker`** | 기본 마커는 아이콘 PNG 를 상대 경로로 찾아 번들러를 거치면 깨진다(broken-marker-icon). 벡터 마커는 이미지 자산이 없어 번들러와 무관하고, 신뢰도를 투명도로 표현할 수 있다 |
| 2026-10-04 | **좌표 변환을 `app/schemas/geo.py` 한 모듈로** | PostGIS POINT 는 (경도, 위도), Leaflet·Google Maps 는 (위도, 경도). 서울(37.5, 127.0)처럼 두 값이 모두 유효 범위면 뒤집혀도 예외가 없고 핀만 중국 동부에 꽂힌다 → 변환 지점을 하나로 모으고 왕복 테스트로 고정. WKB 파싱은 직접 하지 않고 `shapely`(geoalchemy2 권장 조합) 추가 |
| 2026-10-04 | **`POST /api/v1/videos/resolve` — URL→영상 ID 추출을 API 로 노출** | `UNIQUE (user_id, youtube_id)` 때문에 INSERT 하는 쪽(= 클라이언트)이 ID 를 알아야 한다. web·extension 양쪽에 regex 를 복사하면 한쪽만 고쳐지는 날이 온다(단축 URL·`/shorts/`·`/live/` 가 계속 늘어난다) → 규칙은 `schemas/video.py` 한 곳, 왕복 한 번을 감수 |
| 2026-10-04 | **목 응답에 지오코딩 실패 장소를 섞음** | 좌표가 전부 채워진 더미는 거짓 안심을 준다. `lat`/`lng` 가 null 인 항목을 처음부터 넣어 Phase 2 지도 구현이 그 경우를 다루게 강제 |
| 2026-10-04 | **`videos.user_id` 에 DB 레벨 FK 를 걸지 않음** | `auth` 스키마는 Supabase 소유라 Alembic 이 소유권을 주장하면 안 되고, 로컬 Postgres(docker-compose)에는 그 스키마가 없어 마이그레이션이 깨진다. 소유권 강제는 RLS(`auth.uid() = user_id`) + FastAPI JWT 검증. 인덱스(`videos_user_id_idx`)는 RLS 가 모든 질의에 user_id 조건을 붙이므로 필수 |
| 2026-10-04 | **`UNIQUE (user_id, youtube_id)`** | 같은 사용자가 같은 영상을 두 번 넣으면 새 행이 아니라 기존 행 재사용 → Database Webhook 중복 발화에 멱등, 실패 재시도는 같은 행의 status 되돌리기. 대가: **클라이언트가 URL→11자 ID 추출을 담당**해야 함(Phase 2 web·extension 공용 유틸 필요) |
| 2026-10-04 | **RLS(행) + GRANT(컬럼) 2층 권한** | RLS 는 컬럼을 제한하지 못한다. videos 소유자 UPDATE 정책을 열어두면 사용자가 자기 행의 `status`·`cost_usd` 를 덮어써 파이프라인과 비용 집계가 신뢰하는 값이 오염된다 → UPDATE 정책 제거 + `GRANT INSERT (user_id, youtube_url, youtube_id)`, `GRANT SELECT, DELETE`. 제목 수정 기능이 생기면 그때 컬럼 열거 GRANT 와 함께 추가 |
| 2026-10-04 | **스키마 일치를 테스트로 강제** | "모델만 고치고 마이그레이션 빼먹기"는 규칙으로만 두면 반드시 한 번 샌다. metadata DDL vs `alembic upgrade --sql` 문장 비교 + 열거형↔CHECK 대조. DB 없이 돌아 CI 에 넣을 수 있음 |
| 2026-09-18 | **예산(K)을 늘리는 방향 기각 — 병목은 예산이 아니라 선별 신호** | 기존 프레임 표 재계산(`benchmarks/budget_curve.py`): 오라클은 영상당 13장에서 포화(K=16 충분), 무작위는 82장이어야 오라클의 절반, 게이트 통과 766장 전부를 넣어도 27.9곳 < 오라클@16 28곳. 덤: 품질 게이트가 테스트 세트에서 읽을 수 있는 장소를 하나도 잃지 않음(전체 오라클 28 = 게이트 오라클 28) |
| 2026-09-16 | **사전 등록 테스트: `text_nms` 채택 안 함, 기본값 `diverse` 유지** | 테스트 35곳: text-det 4 · full 3 · 무작위 3.9 · 오라클 28. 개발 세트 이득(8 vs 2.7) 재현 실패. 탐색: 박스 수 상위 16장의 읽힘 비율이 기저율보다 낮음(밀집 문자 프레임 = 메뉴·진열대) |
| 2026-09-15 | **선별 후보 `text_nms` 는 사전 등록한 테스트 세트로만 채택 결정** | 개발 세트 3편은 방법 선택에 소진. 채택 규칙: 테스트 합산 text-det ≥ full + 3곳 & > 무작위 기댓값. 검출 입력은 구제본(합성에서 원본 검출이 저조도 2곳 유실) |
| 2026-09-15 | **유튜브 실측: full 4/26 vs 오라클 19/26 → 선별이 무작위 수준으로 판명** | MSER textness 가 실사 프레임 85–92%에서 1.0 포화(AUC≈0.5). PP-OCR DB 검출 박스 수로 고르면 16장에 8/18(무작위 2.7). 개선안은 새 영상으로 재검증 필요 |
| 2026-09-15 | **실영상 검증 입력: 직접 촬영 → 유튜브 URL 매니페스트** | 서비스 입력과 분포를 맞춤(재압축·편집 컷·편집 자막·색보정). 영상은 커밋하지 않고 URL·포맷·구간·정답·sha256만 남김 |
| 2026-09-15 | 유튜브 검증 판정자 **EasyOCR** (합성 장면은 tesseract 유지) | 한글 장면 문자 스모크에서 오라클 tesseract 3/5 vs EasyOCR 5/5. 약한 판정자는 잘못된 ablation 결론을 만듦 |
| 2026-09-15 | 판정 문자열 비교를 **자모 단위**로 | 기존 정규화가 한글을 지워 한글 정답이 조용히 전부 실패. 음절 단위는 을지다방→올지다방(0.75)도 탈락 |
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
  - ⚠️ 임시조치: `packages/shared-types/src/api.ts` placeholder stub(1-2에서 gen-types가 덮어씀), `@pind/ui` lint는 no-op placeholder(0-8에서 eslint 설정)
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
- [x] `vision/dedup.py` — 인접 유사도 샷 분할 + 전역 중복 샷 제거 + 영상별 임계 보정(`adaptive_scene_threshold`) + 예산 컷 다양성 선택(`select_diverse_budget`)
- [x] `vision/select.py` — 오케스트레이터 `select_keyframes`
- [x] `benchmarks/bench_keyframes.py` + `make_sample_video.py` — 단계별 감축 표 · 토큰 절감 · 전후 비교 이미지 · 프레임별 CSV
- [x] `benchmarks/validate_recall.py` + `make_recall_scene.py` — **장소 보존률** 검증 (외부 OCR 판정, 오라클 대비, ablation 4종, 손실 원인 분류)
- [x] 단위/엔드투엔드 테스트 79개, ruff(ANN) + mypy strict 통과
- [x] 반영 시 검증 실패 수정 — opencv `<5` 고정, mypy no-untyped-call (aca77d7)
- [x] `vision-embed` extra에 torchvision·pillow 추가, `auto`가 DINOv3 로드 실패(OSError)도 폴백 (c81dbb4)
- [x] 임베더별 권장 유사도 임계 — DINOv3에 pHash 임계 적용 시 장소 유실 발견·수정 (테스트 68개)
- [x] **장소 보존률 검증 하네스** — 감축률이 아니라 "무엇을 잃었는가"를 재는 방식으로 전환.
      결함 5개 발견·수정 후 합성 장면에서 오라클 동률 달성 (6/8 → **8/8**, 프레임 16 → 12,
      장소당 프레임 2.3 → 1.5). 상세: [docs/vision-frontend.md](docs/vision-frontend.md)
  - [x] 전역 퍼센타일 블러 컷 → ±3초 이웃 중앙값 기준 (선명한 저텍스처 장면이 통째로 탈락했음)
  - [x] 이어지는 흔들림용 절대 하한 추가 (영상 중앙값의 5%)
  - [x] 구제 프레임/정상 노출 프레임 선명도 스케일 계층화 (CLAHE가 lapvar를 ~1.8배 올림)
  - [x] 고정 장면 유사도 임계 → 영상별 분포 기반 보정 (`max_shot_cut_rate`)
  - [x] 예산 컷 점수 순 → 장면 다양성 순 (k-center greedy)
  - [x] 보정이 문자 영역을 줄이면 구제본으로 되돌리는 가드 (`enhance_textness_drop_limit`)
- [x] **유튜브 영상 검증 준비** — `benchmarks/youtube/manifest.json`(후보 3편) + `youtube_fetch.py`
      (다운로드·클립·콘택트 시트·챕터 기반 정답 초안) + `validate_recall.py --manifest`
      (한글 자모 판정, EasyOCR 판정자, 간판/자막 분리, 저조도 auto, OCR 캐시). 테스트 38개 추가(117개)
- [x] **유튜브 영상 검증 실행** (32ce45c 라벨) — full **4/26**, 오라클 19/26, no-dedup(≤200장) 13/26.
      프레임 단위 판정 표로 원인 분해: 예산이 아니라 선별 기준(textness 포화) 문제. 상세: docs/vision-frontend.md
- [x] `selection_strategy="text_nms"` 구현 — PP-OCRv4 DB 검출기 onnxruntime 재구현(`textdet.py`, 원본과 626/626 일치),
      박스 수 + 시간 간격 예산 컷(`budget.py`), 하네스 `text-det` ablation·`--full-table` 무작위 기댓값·`split`.
      개발 세트 실제 코드 8/18 (시뮬레이션과 동일), 합성 7/8. 테스트 130개. **기본값은 diverse 유지**
- [x] 사전 등록 `benchmarks/youtube/PREREGISTRATION.md` — 테스트 3편·예비 3편, 채택 규칙(text-det ≥ full+3 & > 무작위)
- [x] 테스트 3편 라벨·구간 커밋(결과 전) → 사전 등록 명령 실행 → **text-det 4 vs full 3 vs 무작위 3.9 vs 오라클 28 (35곳) → 채택 안 함, diverse 유지**
- [x] 설계 결정·실패 기록 문서화 — [docs/vision-frontend-decisions.md](docs/vision-frontend-decisions.md) (결정 18개, 교훈, 현재 상태)
- [x] **예산 K–회수 곡선** (`benchmarks/budget_curve.py`, 테스트 146개) — 기존 프레임 표 재계산.
      오라클은 영상당 13장에서 포화(K=16 충분), 무작위는 게이트 통과 766장 전부를 넣어도 27.9곳 < 오라클@16 28곳.
      **예산 방향 기각** + 게이트가 테스트 세트에서 장소를 잃지 않음을 확인. 상세: [docs/vision-frontend-budget.md](docs/vision-frontend-budget.md)
- [ ] 다음 방향 결정 (문자 인식 기반 선택 / 자막·음성 신호) — 새 테스트 세트 사전 등록 필요
- [x] DINOv3 vs pHash 비교 — 합성 영상에서 수행 (임계 보정 후 perceptual 53→6장, dinov3 53→5장, 장소 4/4)
- [ ] DINOv3 vs pHash **실영상** 재방문 판정 비교 + 임베더별 임계 재조정
- [ ] 문자 점수 정규화 상수 실사 분포로 재튜닝
- [ ] `analyze_vision`(Gemini Vision) 연결 — Phase 3-1에서

## Phase 1: DB & DTO (Backend)

- [x] 1-1. `Video`, `Place` SQLAlchemy 모델 — `app/models/{enums,video,place}.py`.
      UUID PK, `TimestampMixin`(timezone-aware, `sort_order` 로 컬럼 순서 고정),
      `StrEnum` + `String` + CHECK 제약(`VideoStatus` 6단계 / `SourceModality` 4종),
      `Geography(POINT, 4326)`(지오코딩 실패 시 NULL 허용), places→videos FK CASCADE.
      `app/models/__init__.py` 가 전부 재노출하고 `alembic/env.py` 가 그 패키지를 임포트
      (base 만 임포트하면 metadata 가 비어 autogenerate 가 테이블을 못 봄)
- [x] 1-1. Alembic 초기 마이그레이션 `20261004_1200_initial_videos_places.py` —
      손으로 작성(autogenerate 는 PostGIS extension·geography·GeoAlchemy2 자동 인덱스를
      제대로 못 다룸). `CREATE EXTENSION IF NOT EXISTS postgis` 포함, downgrade 에서
      extension 은 남김. **DB 적용은 JUN 터미널에서** (`make migrate`)
- [x] 1-1. GIST 인덱스 + FK 인덱스 — `places_geom_idx`(gist), `places_video_id_idx`,
      `places_google_place_id_idx`, `videos_user_id_idx`, `videos_youtube_id_idx`.
      `Geography(spatial_index=False)` 로 GeoAlchemy2 자동 인덱스를 끄고 이름을 직접 지정
      (중복 인덱스 방지, supabase/CLAUDE.md 규약과 이름 일치)
- [x] 1-1. RLS 정책 SQL 보강 (`supabase/migrations/20260520000001_...sql`) —
      **행 단위 RLS + 컬럼 단위 GRANT 2층 구조로 변경.** videos 소유자 UPDATE 정책을
      제거하고 `GRANT INSERT (user_id, youtube_url, youtube_id)` 만 허용.
      RLS 는 "어떤 행"만 정하고 "어떤 컬럼"은 정하지 못해서, UPDATE 를 열어두면
      클라이언트가 자기 행의 `status='completed'`·`cost_usd=0` 을 덮어쓸 수 있었음
- [x] 1-1. 스키마 드리프트 테스트 `tests/unit/test_models_schema.py` (12개, 총 158개) —
      모델 metadata DDL(mock engine)과 마이그레이션 offline DDL(`upgrade --sql`)을
      문장 단위로 비교(나열 순서는 정규화). 열거형↔CHECK 제약 일치, geom 타입·SRID,
      GIST 인덱스 1개, FK CASCADE·이름, user_id 에 DB FK 없음까지 검사.
      마이그레이션에 컬럼을 하나 더 넣어 실제로 실패하는지 확인함
- [x] 1-2. Pydantic 스키마 — `app/schemas/{geo,pagination,place,video}.py`.
      `PlaceRead` 는 `geom`(WKB) 을 `lat`/`lng` 로 펼쳐 내보내고 WKB 는 노출하지 않는다.
      좌표 변환은 `geo.py` 한 모듈에만 둔다(PostGIS 는 (경도,위도), 지도 API 는
      (위도,경도) — 서울처럼 둘 다 유효 범위면 뒤집혀도 예외 없이 핀만 엉뚱한 곳에
      꽂힌다). 커서 페이지네이션 `Page[T]`(offset 금지, 커서는 불투명 base64)
- [x] 1-2. `GET /api/v1/places` mock 라우터 + `/api/v1/videos` —
      본문은 더미지만 `response_model` 과 OpenAPI 는 실제 스키마. 더미에 **지오코딩
      실패 장소(좌표 null)를 하나 섞어** 지도 쪽이 처음부터 그 경우를 다루게 함.
      `POST /videos/resolve` 추가: URL→11자 ID 추출 규칙을 `schemas/video.py` 한 곳에
      두고 노출(web·extension 양쪽에 regex 를 복사하면 한쪽만 고쳐지는 날이 온다)
- [x] 1-2. `make gen-types` 파이프라인 — `packages/shared-types/src/api.ts` placeholder
      교체 완료(383줄, `PlaceRead`·`VideoRead`·`VideoStatus`·`SourceModality` 포함),
      `pnpm --filter=@pind/shared-types typecheck` 통과. `openapi.json` 은 중간 산출물로
      gitignore. Makefile 폴백에 `ensure_ascii=False` 추가(한글 설명이 \uXXXX 로 깨짐).
      문서의 `make gen:types` 표기를 실제 타깃명 `make gen-types` 로 정정
- [x] 1-2. 단위 테스트 52개 추가 (총 210개) — `test_schemas.py`(37): 좌표 왕복·반쪽
      좌표 거부·범위 검증·EWKB hex 해석·URL 9종 동일 ID·ID 불일치 거부·커서 왕복.
      `test_routers_mock.py`(15): 응답 모양, lat/lng 노출·geom 비노출, 좌표 null 사례,
      잘못된 커서는 400(500 아님), 모든 라우트가 `/api/v1` + tags 보유
- [ ] 1-2. (보류) `make verify` 의 `pnpm lint`/`typecheck` 전체 — 클라우드 컨테이너에
      web·extension `node_modules` 가 없어 미실행. shared-types 만 확인함. 맥에서 확인 필요

## Phase 2: Frontend 뼈대

- [x] 2-1. `packages/shared-types/api.ts` 자동 생성 검증 — `lib/api.ts` 가 `components["schemas"]`
      에서 `PlaceRead`·`VideoRead`·`VideoCreate`·`Page_PlaceRead_` 를 가져오고, 경로는
      `paths` 타입으로 묶어 OpenAPI 에 없는 엔드포인트를 쓰면 타입 에러가 난다
- [x] 2-1. `lib/supabase.ts`, `lib/api.ts` wrapper —
      **supabase 클라이언트를 지연 생성으로 바꿨다.** 모듈 최상단에서 환경변수를 검사해
      throw 하던 코드가 `next build` 를 깨뜨린다(모든 페이지가 `'use client'` 여도 Next 는
      빌드 때 프리렌더를 한 번 돌리고, 그 시점엔 `.env.local` 이 없는 CI 일 수 있다).
      `apiFetch` 는 FastAPI 의 `{detail}`(422 는 배열)을 사람이 읽을 메시지로 변환
- [x] 2-1. Supabase Auth 흐름 — `hooks/useSession.ts`(getSession + `onAuthStateChange`
      둘 다 구독: getSession 만 쓰면 다른 탭의 로그아웃·토큰 갱신을 모른다),
      `app/(auth)/login/page.tsx`(로그인·가입·로그아웃, 이메일 확인 켜진 경우 안내,
      환경변수 없을 때 설정 안내 화면). `ready` 플래그로 세션 복원 중 깜빡임 방지
- [x] 2-2. URL 입력 폼 `components/VideoForm.tsx` — `POST /videos/resolve` 로 ID 를 받고
      `videos` INSERT(클라이언트가 넣을 수 있는 3개 컬럼만). FastAPI 를 직접 부르지 않는 건
      그 INSERT 가 Database Webhook 을 깨우는 설계이기 때문. UNIQUE 위반(23505)은
      에러가 아니라 "이미 등록한 영상" 안내로 처리
- [x] 2-2. 지도 `components/PlacesMap.tsx` — `dynamic(..., { ssr: false })`.
      **기본 마커 대신 `circleMarker`** 를 쓴다(Leaflet 기본 아이콘은 PNG 를 상대 경로로
      찾아 번들러를 거치면 깨지는 알려진 문제 — 벡터 마커는 이미지 자산이 아예 없다).
      신뢰도를 fillOpacity 로 표현. StrictMode 재실행 대비 cleanup 에서 `map.remove()`
- [x] 2-2. mock API 연결 `app/places/page.tsx` — TanStack Query 로 `/api/v1/places` 호출,
      좌표 있는 장소는 지도에, **좌표 없는 장소는 숨기지 않고 목록에만** 표시하고 몇 곳이
      빠졌는지 알린다(목 응답에 일부러 섞어둔 지오코딩 실패 사례가 여기서 쓰인다)
- [x] 2-2. 검증 — `pnpm --filter=@pind/web typecheck/lint/build` 전부 통과.
      환경변수 없이 `next build` 가 7페이지 프리렌더까지 성공(지연 생성 수정의 확인).
      `@pind/ui`·`@pind/shared-types` 도 통과. **extension 은 클라우드에서 미검증**
      (plasmo 가 네이티브 빌드 스크립트를 요구 — 맥에서 `pnpm approve-builds` 후 확인)

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
저조도 프레임 구제로 실내 장소 유실 해결. 유튜브 영상 검증 도구 준비 완료, 실행은 미완.

## 다음 작업

1. **Phase 1-1**: `Video`, `Place` SQLAlchemy 모델(UUID PK, GeoAlchemy2 Geography) + Alembic 초기 마이그레이션(PostGIS extension) + GIST/FK 인덱스 → `alembic upgrade head` → RLS 마이그레이션 `supabase db push`. (복잡 feature → `/pdca plan` 고려)
2. **비전 프론트엔드 다음 방향 결정** — 사전 등록 테스트에서 `text_nms` 기각(4 vs 3, 무작위 3.9). 휴리스틱 추가 조정 대신
   예산-비용 곡선 / 문자 인식 기반 선택 / 자막·음성 신호 중 선택 후 새 테스트 세트로 검증

---

## 알려진 이슈 / 검증 필요

- (Phase 3 진행 시) Gemini Vision의 한글 간판 인식률 — 실측 후 confidence threshold 조정
- (Phase 3 진행 시) Place Resolver의 fuzzy match threshold — 실험으로 튜닝
- (Phase 3 진행 시) yt-dlp가 YouTube의 봇 차단에 막힐 가능성 — 우회/캐싱 전략 필요할 수도
- 비전 프론트엔드: 합성 8/8, **유튜브 dev 4/26 (오라클 19) · test 3/35 (오라클 28, 무작위 3.9)** — 실영상에서 선별이 무작위 수준
- 샷 분할 임계는 이제 영상별로 보정되지만, **재방문 중복 임계는 여전히 고정값**
  (perceptual 0.95 / dinov3 0.97). 같은 가게를 다른 각도로 다시 찍은 컷 병합은 미검증
- 전체 미니 ISP(디노이징·샤프닝)가 합성 장면에서 보존률에 기여하지 못했다(처리 시간 +45%).
  실사에서도 그렇다면 기본값에서 빼는 것이 맞다
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
