# tests/test_gui_smoke.py

def test_gui_import_smoke():
    """
    Проверяем, что GUI модуль импортируется без ошибок.
    Streamlit UI не запускаем — только smoke‑import.
    """
    import aaps_emulator.gui.gui_simulator as gui

    assert gui is not None
    assert hasattr(gui, "ROOT")
    assert hasattr(gui, "DATA_DIR")
