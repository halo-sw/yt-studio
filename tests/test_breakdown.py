"""breakdown.py 검증 — FeiGe식 4단계 역해부 파이프라인."""

from core.breakdown import (
    Shot,
    analyze_rhythm,
    parse_scene_times,
    pick_representative,
    prepare,
    run_breakdown,
    to_material,
)
from core.schemas import Track


def test_parse_scene_times_builds_shots():
    stderr = "pts_time:2.5\n...pts_time:7.1\npts_time:7.15\n"  # 7.1→7.15는 노이즈
    shots = parse_scene_times(stderr, total_duration=12.0)
    assert [s.start for s in shots] == [0.0, 2.5, 7.15]
    assert shots[-1].end == 12.0


def test_pick_representative_covers_timeline():
    shots = [Shot(i + 1, i * 1.0, (i + 1) * 1.0) for i in range(40)]  # 40초·40샷
    picked = pick_representative(shots, k=12)
    assert len(picked) == 12
    # 균등 커버리지: 마지막 버킷(33초 이후)에서도 뽑혔는지
    assert any(s.start >= 33 for s in picked)
    # 12개 이하면 그대로
    assert len(pick_representative(shots[:5], k=12)) == 5


def test_rhythm_and_hook_density():
    shots = [Shot(1, 0, 1.5), Shot(2, 1.5, 3.0), Shot(3, 3.0, 9.0), Shot(4, 9.0, 20.0)]
    r = analyze_rhythm(shots)
    assert r.shot_count == 4 and r.hook_cuts == 4 - 0  # 4번 샷 start=9.0 < 10 포함
    assert r.avg_cut == 5.0


def test_prepare_falls_back_without_ffmpeg_file():
    shots = prepare("/no/such/file.mp4", total_duration=28.0)
    assert len(shots) >= 6 and abs(shots[-1].end - 28.0) < 0.1


def test_run_breakdown_e2e_mock():
    study, collage = run_breakdown("/no/file.mp4", "https://youtu.be/ref123",
                                   total_duration=60.0, api_key=None)
    assert len(collage) <= 12
    assert study.palette and study.hook_structure
    hint = study.conte_hint()
    # 콘테 힌트에 스타일 참조 + 저작권 가드 문구
    assert "훅 문법" in hint and "원본 재현 금지" in hint


def test_to_material_enforces_format_reuse():
    study, _ = run_breakdown("/no/file.mp4", "https://youtu.be/ref123", 60.0)
    m = to_material(study, Track.NATEPAN, "버스정류장 3분 로맨스 — 우리 버전")
    assert m["source_type"] == "breakdown"
    assert "구조 응용" in m["summary"]      # 규칙 5-5: 모방 아님 명시
    assert m["conte_hint"].startswith("[스타일 참조")
