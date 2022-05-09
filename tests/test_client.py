from tkinter import W

from ruv_dl import ruv_client


def test_fields():
    programs = ruv_client.RUVClient().get_all_programs()
    assert len(programs) > 0
    for program in programs.values():
        assert program["title"], f"Bad program: {program}"
        # Most Icelandic shows do not have a foreign title
        assert "foreign_title" in program, f"Bad program: {program}"
        assert program["id"], f"Bad program: {program}"
        # Some audio shows do not have a short description
        assert "short_description" in program, f"Bad program: {program}"
        assert "episodes" in program, f"Bad program: {program}"
        # Some programs have now episodes
        for episode in program["episodes"]:
            assert "id" in episode, f"Bad episode: {episode}"
            assert "title" in episode, f"Bad episode: {episode}"
            assert "firstrun" in episode, f"Bad episode: {episode}"
            assert "file" in episode, f"Bad episode: {episode}"
