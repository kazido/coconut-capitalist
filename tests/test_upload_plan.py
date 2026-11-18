from pathlib import Path

from scripts.upload_emojis import MAX_BYTES, EmojiFile, find_files, plan_upload


def f(name, size=1000, ext=".png"):
    return EmojiFile(name, Path(f"art/out/{name}{ext}"), size)


def names(files):
    return [x.name for x in files]


def test_only_missing_names_are_uploaded():
    plan = plan_upload({"material_iron_ore"}, [f("material_iron_ore"), f("material_gold_ore"), f("pet_ember", ext=".webp")])
    assert names(plan.upload) == ["material_gold_ore", "pet_ember"]
    assert plan.skipped == ["material_iron_ore"] and not plan.replace and not plan.invalid
    assert plan.slots_used == 3


def test_replace_recreates_an_existing_emoji_without_using_a_slot():
    plan = plan_upload({"material_iron_ore", "material_gold_ore"}, [f("material_iron_ore"), f("material_gold_ore")], replace=["material_iron_ore"])
    assert names(plan.replace) == ["material_iron_ore"] and not plan.upload and plan.skipped == ["material_gold_ore"]
    assert plan.slots_used == 2


def test_replace_without_a_file_is_reported():
    plan = plan_upload({"a_b"}, [], replace=["a_b"])
    assert plan.invalid and plan.invalid[0][0] == "a_b"


def test_only_prefix_filters():
    plan = plan_upload(set(), [f("ui_releaf"), f("ui_home"), f("material_iron_ore")], only="ui_")
    assert names(plan.upload) == ["ui_home", "ui_releaf"] and plan.skipped == ["material_iron_ore"]


def test_limit_defers_the_rest_for_the_next_run():
    plan = plan_upload(set(), [f(n) for n in ("aa", "bb", "cc", "dd")], limit=2)
    assert names(plan.upload) == ["aa", "bb"] and plan.deferred == ["cc", "dd"]
    assert names(plan_upload({"aa", "bb"}, [f(n) for n in ("aa", "bb", "cc", "dd")], limit=2).upload) == ["cc", "dd"]  # resumed


def test_invalid_names_and_oversized_or_empty_files_never_upload():
    files = [f("Iron_Ore"), f("x"), f("a" * 33), f("has-dash"), f("big_one", MAX_BYTES + 1), f("empty", 0), f("fine_one", MAX_BYTES)]
    plan = plan_upload(set(), files)
    assert names(plan.upload) == ["fine_one"]
    assert {n for n, _ in plan.invalid} == {"Iron_Ore", "x", "a" * 33, "has-dash", "big_one", "empty"}


def test_two_files_with_one_name_are_ambiguous():
    plan = plan_upload(set(), [f("dup_one"), f("dup_one", ext=".gif")])
    assert not plan.upload and plan.invalid[0][0] == "dup_one"


def test_slots_run_out_at_the_cap():
    plan = plan_upload({"aa", "bb"}, [f("cc"), f("dd")], max_slots=3)
    assert names(plan.upload) == ["cc"] and plan.deferred == ["dd"] and plan.slots_used == 3


def test_find_files_reads_a_folder(tmp_path):
    (tmp_path / "material_iron_ore.png").write_bytes(b"x" * 10)
    (tmp_path / "spin.webp").write_bytes(b"y")
    (tmp_path / "notes.txt").write_text("no")
    found = find_files(tmp_path)
    assert names(found) == ["material_iron_ore", "spin"] and found[0].size == 10
    assert find_files(tmp_path / "missing") == []


def test_only_suffix_filters():
    plan = plan_upload(set(), [f("rod_iron_tip"), f("tidecaller_rod"), f("material_iron_ore")], only_suffix="_rod")
    assert names(plan.upload) == ["tidecaller_rod"]


def test_delete_only_removes_names_that_exist_and_reports_the_rest():
    from scripts.upload_emojis import plan_delete

    gone, missing = plan_delete({"flame_ash", "material_iron_ore"}, ["flame_ash", "flame_blue", "flame_ash"])
    assert gone == ["flame_ash"] and missing == ["flame_blue"]  # (no duplicates, and a name not on Discord is only reported)
