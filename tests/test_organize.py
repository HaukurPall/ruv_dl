from ruv_dl.organize import _guess_show_num


def test_guess_show_number_ruv_thattur():
    show_name = "Þáttur 1 af 26"
    assert _guess_show_num(show_name) == (1, 1)


def test_guess_show_number_ruv_missing():
    show_name = "Þessi þáttur heitir eitthvað"
    assert _guess_show_num(show_name) == None


def test_guess_show_number_Exx():
    show_name = "E23"
    assert _guess_show_num(show_name) == (23, 23)


def test_guess_show_number_Exx_Eyy():
    show_name = "E23-E24"
    assert _guess_show_num(show_name) == (23, 24)
