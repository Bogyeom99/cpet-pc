import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")


def test_desktop_application_imports_without_web_server():
    from ui.main_window import MainWindow
    from services import athlete_store

    assert MainWindow.__name__ == "MainWindow"
    assert athlete_store.is_configured()
