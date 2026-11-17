from pathlib import Path

from scripts.quick_tests import MAX_FILES, select_tests


def _make_tests(tests_dir: Path, files: dict[str, str]) -> None:
    tests_dir.mkdir(exist_ok=True)
    for name, text in files.items():
        (tests_dir / name).write_text(text, encoding="utf-8")


def test_service_change_selects_its_test(tmp_path):
    _make_tests(tmp_path, {"test_foraging.py": "from x import foraging\n", "test_fishing.py": "fishing only\n"})
    chosen, _ = select_tests(["cococap/services/foraging.py"], tmp_path)
    assert chosen == ["tests/test_foraging.py"]


def test_generic_stem_runs_only_registry_tests(tmp_path):
    _make_tests(tmp_path, {"test_registry.py": "x\n", "test_models.py": "models models\n"})
    chosen, notes = select_tests(["cococap/services/models.py"], tmp_path)
    assert chosen == ["tests/test_registry.py"]
    assert notes


def test_art_and_docs_select_nothing(tmp_path):
    _make_tests(tmp_path, {"test_foraging.py": "foraging\n"})
    assert select_tests(["art/x.png", "docs/DESIGN.md", "data/cococap.db"], tmp_path) == ([], [])


def test_changed_test_file_selects_itself(tmp_path):
    _make_tests(tmp_path, {})
    chosen, _ = select_tests(["tests/test_quick_tests.py"], tmp_path)
    assert chosen == ["tests/test_quick_tests.py"]


def test_cap_reports_skipped_files(tmp_path):
    files = {f"test_m{i:02d}.py": "mining here\n" for i in range(MAX_FILES + 2)}
    _make_tests(tmp_path, files)
    chosen, notes = select_tests(["configs/mining.toml"], tmp_path)
    assert len(chosen) == MAX_FILES
    assert any("skipped 2" in note for note in notes)
