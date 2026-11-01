import os
import threading
from pathlib import Path

import pytest

GROUPS_ENV = "YOUTAB_TEST_GROUPS"
GROUP_ENV = "YOUTAB_TEST_GROUP"


def _test_group():
    """環境変数から (組の数, 担当の組) を読む。両方なければ None。不正なら UsageError。"""
    groups_raw = os.environ.get(GROUPS_ENV)
    group_raw = os.environ.get(GROUP_ENV)
    if groups_raw is None and group_raw is None:
        return None
    if groups_raw is None or group_raw is None:
        raise pytest.UsageError(f"{GROUPS_ENV} と {GROUP_ENV} は両方とも設定してください")
    try:
        groups = int(groups_raw)
        group = int(group_raw)
    except ValueError:
        raise pytest.UsageError(
            f"{GROUPS_ENV}={groups_raw!r} と {GROUP_ENV}={group_raw!r} は整数で指定してください"
        ) from None
    if groups < 1:
        raise pytest.UsageError(f"{GROUPS_ENV} は 1 以上にしてください（{groups}）")
    if not 0 <= group < groups:
        raise pytest.UsageError(f"{GROUP_ENV} は 0〜{groups - 1} にしてください（{group}）")
    return groups, group


def pytest_configure(config):
    """組の環境変数の誤りを、収集の前（xdist ではワーカーを起こす前）に知らせて止める。"""
    _test_group()


def pytest_collection_modifyitems(config, items):
    """テスト全体を N 個の組に分け、そのうち 1 組だけを走らせる。

    CI でテストを複数のジョブに分けて同時に走らせるための仕組み。
    YOUTAB_TEST_GROUPS が組の数 N、YOUTAB_TEST_GROUP が担当の組（0〜N-1）。
    収集順で i 番目のテストは i % N の組に入るので、全組を合わせると全件になり、重複もない。
    両方とも無ければ何もしない（全件を走らせる）。片方だけ・整数でない・範囲外なら起動を止める。

    手元で 1 組だけ走らせる例:
        env YOUTAB_TEST_GROUPS=4 YOUTAB_TEST_GROUP=0 uv run pytest

    組の中身を調べるときは、addopts の -n auto を打ち消すため -n0 を付ける
    （例: ... uv run pytest -n0 --collect-only -q）。

    N をテストの件数より大きくすると空の組ができ、その組は pytest が「テストなし」
    （終了コード 5）として失敗する。
    """
    selected = _test_group()
    if selected is None:
        return
    groups, group = selected
    keep, drop = [], []
    for i, item in enumerate(items):
        (keep if i % groups == group else drop).append(item)
    if drop:
        config.hook.pytest_deselected(items=drop)
    items[:] = keep


@pytest.fixture(autouse=True)
def isolate_agent_settings(tmp_path_factory, monkeypatch):
    """利用者の本物の設定と環境変数を読まないよう、設定の場所を空の一時フォルダへ向ける。"""
    base = tmp_path_factory.mktemp("agent-config")
    for env, name in (("CLAUDE_CONFIG_DIR", "claude"), ("CODEX_HOME", "codex")):
        (base / name).mkdir()
        monkeypatch.setenv(env, str(base / name))
    for env in ("ANTHROPIC_MODEL", "CLAUDE_CODE_EFFORT_LEVEL"):
        monkeypatch.delenv(env, raising=False)


PROBED = {"width": 1920, "height": 1080, "duration": 12.5}

SERVE_POLL_INTERVAL = 0.01


def serve_in_thread(httpd):
    """httpd を別スレッドで動かす。止める合図（shutdown）を SERVE_POLL_INTERVAL 秒おきに確かめる。"""
    threading.Thread(
        target=httpd.serve_forever,
        kwargs={"poll_interval": SERVE_POLL_INTERVAL},
        daemon=True,
    ).start()
    return httpd


@pytest.fixture
def fake_probe(monkeypatch):
    """add.probe の偽物（ffprobe を使わない）。確かめたパスを順に記録したリストを返す。

    中身によらず、映像の入った動画（PROBED の幅・高さ・長さ）として通す。
    """
    from youtab import add

    seen: list[Path] = []

    def probe(path):
        seen.append(Path(path))
        return dict(PROBED)

    monkeypatch.setattr(add, "probe", probe)
    return seen


@pytest.fixture
def plain_ids(monkeypatch, fake_probe):
    """取り込んだ曲の ID を、乱数を付けずにファイル名（拡張子を除く）にする。add.probe も偽物にする。"""
    from youtab import add

    monkeypatch.setattr(add, "new_id", lambda name: Path(name).stem)
