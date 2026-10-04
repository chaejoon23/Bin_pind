-- Migration: RLS policies + column grants for videos and places
--
-- 적용 순서:
--   1. Phase 1-1: Alembic이 videos, places 테이블 생성 (apps/api/alembic/versions/)
--   2. 이 파일: supabase db push 로 RLS 활성화 + 정책/권한 추가
--
-- FastAPI는 service_role 키를 사용하므로 RLS를 자동 우회함.
-- 클라이언트(anon / authenticated)는 아래 정책 + 권한으로만 접근 가능.
--
-- ─────────────────────────────────────────────────────────────────────────────
-- 설계 메모 — RLS만으로는 부족하다
--
-- RLS는 "어떤 행"을 만질 수 있는지만 정한다. "어떤 컬럼"은 정하지 못한다.
-- videos 에 소유자 UPDATE 정책을 열어두면, 사용자가 자기 행의 status 를
-- 'completed' 로 바꾸거나 cost_usd 를 0 으로 덮어쓸 수 있다. 둘 다 파이프라인과
-- 비용 집계가 신뢰하는 값이다. 그래서 이 파일은 두 층으로 막는다.
--
--   층 1 (행): RLS 정책 — 남의 행에 손대지 못함.
--   층 2 (컬럼): GRANT — 클라이언트가 쓸 수 있는 컬럼을 열거한 것만 허용.
--
-- 결론: 클라이언트는 영상을 넣고(3개 컬럼), 자기 것을 읽고, 지울 수 있다.
-- status·cost_usd·메타데이터는 service_role(FastAPI)만 쓴다.
-- ─────────────────────────────────────────────────────────────────────────────


-- ─────────────────────────────────────────────────────────────────────────────
-- videos
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE videos ENABLE ROW LEVEL SECURITY;

CREATE POLICY "videos_owner_select" ON videos
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "videos_owner_insert" ON videos
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "videos_owner_delete" ON videos
  FOR DELETE USING (auth.uid() = user_id);

-- UPDATE 정책 없음 → RLS 기본 deny.
-- 제목 수정 같은 기능이 생기면 그때 컬럼을 열거한 GRANT UPDATE (title) 와
-- 소유자 UPDATE 정책을 같은 마이그레이션에 함께 추가한다.

-- 층 2: 컬럼 권한. Supabase 기본 설정이 public 스키마에 넓은 권한을 주므로
-- 먼저 회수하고 필요한 것만 다시 부여한다.
REVOKE ALL ON videos FROM anon, authenticated;
GRANT SELECT, DELETE ON videos TO authenticated;
GRANT INSERT (user_id, youtube_url, youtube_id) ON videos TO authenticated;


-- ─────────────────────────────────────────────────────────────────────────────
-- places
--   SELECT 전용: 본인 video 에 속한 place 만 조회 가능.
--   INSERT/UPDATE/DELETE: 정책 없음 → RLS 기본 deny (FastAPI service_role만 write).
--   video 가 지워지면 FK ON DELETE CASCADE 로 함께 사라진다.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE places ENABLE ROW LEVEL SECURITY;

CREATE POLICY "places_owner_select" ON places
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM videos
       WHERE videos.id      = places.video_id
         AND videos.user_id = auth.uid()
    )
  );

REVOKE ALL ON places FROM anon, authenticated;
GRANT SELECT ON places TO authenticated;


-- ─────────────────────────────────────────────────────────────────────────────
-- Realtime publication
--   RLS가 Realtime에도 적용되므로 본인 row 변경만 수신됨.
--   videos.status 진행 표시와 places INSERT(지도 마커 추가)를 클라이언트가 구독한다.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER PUBLICATION supabase_realtime ADD TABLE videos, places;
