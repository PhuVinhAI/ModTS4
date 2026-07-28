import os
import sys

import pytest


@pytest.fixture
def decompile_cli(mock_settings, tmp_path):
    mock_settings.num_threads = 2
    mock_settings.decompiler_timeout = 10.0
    mock_settings.gameplay_folder_data = str(tmp_path / "gameplay")
    mock_settings.gameplay_folder_game = str(tmp_path / "python")
    mock_settings.projects_python_path = str(tmp_path / "decompile" / "output" / "python")
    mock_settings.decompile_output_folder = str(tmp_path / "decompile" / "output")

    sys.modules.pop("decompile", None)
    import decompile
    return decompile


class TestDecompileCli:
    def test_parser_accepts_installed_mod_folder(self, decompile_cli):
        args = decompile_cli.build_parser().parse_args(
            ["--mod", os.path.join("C:\\Mods", "ExampleMod")]
        )

        assert args.mod.endswith("ExampleMod")
        assert not args.game
        assert not args.folder

    def test_mod_mode_uses_configured_output_root(
        self, decompile_cli, mock_settings, tmp_path, monkeypatch, capsys
    ):
        mod_folder = str(tmp_path / "Mods" / "ExampleMod")
        calls = []

        monkeypatch.setattr(decompile_cli, "decompile_pre", lambda: calls.append("pre"))
        monkeypatch.setattr(
            decompile_cli,
            "decompile_mod_folder",
            lambda src, dst: calls.append((src, dst)) or os.path.join(dst, "mods", "ExampleMod"),
        )
        monkeypatch.setattr(decompile_cli, "decompile_print_totals", lambda: None)

        result = decompile_cli.main(["--mod", mod_folder])

        assert result == 0
        assert calls == [
            "pre",
            (mod_folder, mock_settings.decompile_output_folder),
        ]
        assert os.path.join("mods", "ExampleMod") in capsys.readouterr().out

    def test_modes_are_mutually_exclusive(self, decompile_cli):
        with pytest.raises(SystemExit):
            decompile_cli.build_parser().parse_args(["--game", "--mod", "ExampleMod"])
