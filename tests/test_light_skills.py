from tests.test_hub import all_text, buttons, hub


async def test_light_tab_shows_smithing_and_its_level(db):
    nav, _ = await hub("skills", tab="light")
    text = all_text(nav)
    assert "Smithing" in text
    assert "Lv 1" in text
    assert "Max part tier" in text
    assert "Light skills" not in text
    assert "Smith tools on Tools -> Smithing" in text


async def test_old_skills_tab_still_renders_the_main_skills(db):
    nav, _ = await hub("skills")
    text = all_text(nav)
    assert all(name in text for name in ("Mining", "Farming", "Foraging", "Fishing", "Combat"))
    assert len([b for b in buttons(nav) if b.label == "Open"]) == 4
