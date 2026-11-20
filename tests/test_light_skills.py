from tests.test_hub import all_text, buttons, hub


async def test_the_skills_page_lists_smithing_with_its_level(db):
    nav, _ = await hub("skills")
    text = all_text(nav)
    assert "Smithing" in text and "Lv 1" in text


async def test_the_smithing_row_opens_the_smithing_page(db):
    nav, inter = await hub("skills")
    await [b for b in buttons(nav) if b.label == "Open"][-1].callback(inter)  # smithing is the last row with an Open button
    assert nav.screen.id == "smithing"
