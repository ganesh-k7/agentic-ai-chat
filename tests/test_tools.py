import pytest

from agent.config import settings
from agent.tools import list_files, read_file, write_file


@pytest.fixture(autouse=True)
def tmp_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_dir", tmp_path)
    return tmp_path


def test_write_then_read():
    write_file.invoke({"path": "sub/hello.txt", "content": "hi"})
    assert read_file.invoke({"path": "sub/hello.txt"}) == "hi"
    assert "sub/hello.txt" in list_files.invoke({})


def test_cannot_escape_workspace():
    with pytest.raises(ValueError):
        read_file.invoke({"path": "../../etc/passwd"})
