import json
import os
import time
from ctypes import Structure, c_uint
from multiprocessing.sharedctypes import Value
from subprocess import CompletedProcess

import pytest


@pytest.fixture(autouse=True)
def _mock_settings(mock_settings):
    mock_settings.num_threads = 2
    mock_settings.decompiler_timeout = 10.0


class TestStats:
    def test_manager_is_not_started_during_import(self):
        import util.decompile as decompile_mod

        assert decompile_mod._manager is None

    def test_stats_structure(self):
        from util.decompile import Stats
        s = Value(Stats, 0, 0, 0, 0)
        assert s.suc_count == 0
        assert s.fail_count == 0
        assert s.count == 0
        assert s.col_count == 0

    def test_total_stats_structure(self):
        from util.decompile import TotalStats
        t = Value(TotalStats, 0, 0, 0, 0)
        assert t.suc_count == 0
        assert t.minutes == 0


class TestPrintProgress:
    def test_success_increments(self):
        from util.decompile import Stats, TotalStats, print_progress
        stats = Value(Stats, 0, 0, 0, 0)
        total = Value(TotalStats, 0, 0, 0, 0)

        print_progress(stats, total, True)
        assert stats.suc_count == 1
        assert stats.fail_count == 0
        assert stats.count == 1
        assert total.suc_count == 1

    def test_failure_increments(self):
        from util.decompile import Stats, TotalStats, print_progress
        stats = Value(Stats, 0, 0, 0, 0)
        total = Value(TotalStats, 0, 0, 0, 0)

        print_progress(stats, total, False)
        assert stats.fail_count == 1
        assert stats.suc_count == 0
        assert stats.count == 1
        assert total.fail_count == 1

    def test_col_count_wraps_at_80(self):
        from util.decompile import Stats, TotalStats, print_progress
        stats = Value(Stats, 0, 0, 0, 0)
        total = Value(TotalStats, 0, 0, 0, 0)

        for _ in range(80):
            print_progress(stats, total, True)
        assert stats.col_count == 0  # reset after 80


class TestPrintSummary:
    def test_outputs_stats(self, capsys):
        from util.decompile import Stats, print_summary
        stats = Value(Stats, 7, 3, 10, 0)

        print_summary(stats)
        output = capsys.readouterr().out
        assert "S: 7" in output
        assert "F: 3" in output
        assert "T: 10" in output
        assert "70.0%" in output
        assert "30.0%" in output


class TestInitProcess:
    def test_sets_process_module_globals(self):
        from util.decompile import init_process, Stats, TotalStats
        from util import process_module

        stats = Value(Stats, 0, 0, 0, 0)
        total = Value(TotalStats, 0, 0, 0, 0)
        failed_files = []

        init_process(stats, total, failed_files)
        assert process_module.stats is stats
        assert process_module.total_stats is total
        assert process_module.failed_files is failed_files


class TestStdoutDecompile:
    def test_writes_stdout_to_file(self, tmp_path):
        from util.decompile import stdout_decompile

        dest = str(tmp_path / "output.py")
        # Use python3 to echo some text to stdout
        success, result = stdout_decompile(
            "python3", ["-c", "print('decompiled code')"], dest
        )

        assert success
        assert os.path.isfile(dest)
        with open(dest) as f:
            assert "decompiled code" in f.read()

    def test_returns_false_on_failure(self, tmp_path):
        from util.decompile import stdout_decompile

        dest = str(tmp_path / "output.py")
        success, result = stdout_decompile(
            "python3", ["-c", "import sys; sys.exit(1)"], dest
        )
        assert not success

    def test_does_not_write_on_failure(self, tmp_path):
        from util.decompile import stdout_decompile

        dest = str(tmp_path / "output.py")
        success, result = stdout_decompile(
            "python3", ["-c", "print('bad output'); import sys; sys.exit(1)"], dest
        )
        assert not success
        assert not os.path.isfile(dest)


class TestDecompilePrintTotals:
    def test_with_results(self, capsys):
        from util.decompile import TotalStats, decompile_print_totals, totals
        totals.suc_count = 8
        totals.fail_count = 2
        totals.count = 10
        totals.minutes = 5

        decompile_print_totals()
        output = capsys.readouterr().out
        assert "S: 8" in output
        assert "F: 2" in output
        assert "T: 10" in output

        # Reset globals
        totals.suc_count = 0
        totals.fail_count = 0
        totals.count = 0
        totals.minutes = 0

    def test_with_zero_count(self, capsys):
        from util.decompile import decompile_print_totals, totals
        totals.count = 0

        decompile_print_totals()
        output = capsys.readouterr().out
        assert "No files were processed" in output


class TestStreamingDecompile:
    def test_normal_output(self, tmp_path):
        from util.decompile import streaming_decompile

        dest = str(tmp_path / "output.py")
        wrote, lines = streaming_decompile(
            "python3", ["-c", "print('line1'); print('line2')"], dest
        )
        assert wrote is True
        assert lines == 2
        with open(dest) as f:
            content = f.read()
        assert "line1" in content
        assert "line2" in content

    def test_kills_runaway_indentation(self, tmp_path):
        from util.decompile import streaming_decompile, _max_indent

        dest = str(tmp_path / "output.py")
        # Print one normal line, then one with excessive indentation
        code = (
            "print('good line')\n"
            "print(' ' * {} + 'bad line')".format(_max_indent + 10)
        )
        wrote, lines = streaming_decompile(
            "python3", ["-c", code], dest
        )
        assert wrote is True
        assert lines == 1  # only the good line should be kept
        with open(dest) as f:
            content = f.read()
        assert "good line" in content
        assert "bad line" not in content

    def test_returns_false_on_no_output(self, tmp_path):
        from util.decompile import streaming_decompile

        dest = str(tmp_path / "output.py")
        wrote, lines = streaming_decompile(
            "python3", ["-c", "import sys; sys.exit(1)"], dest
        )
        assert wrote is False
        assert lines == 0

    def test_returns_false_on_bad_command(self, tmp_path):
        from util.decompile import streaming_decompile

        dest = str(tmp_path / "output.py")
        wrote, lines = streaming_decompile(
            "/nonexistent/binary", [], dest
        )
        assert wrote is False
        assert lines == 0

    def test_kills_silent_process_on_timeout(self, tmp_path, mock_settings):
        from util.decompile import streaming_decompile

        mock_settings.decompiler_timeout = 0.1
        dest = str(tmp_path / "output.py")
        started = time.monotonic()
        wrote, lines = streaming_decompile(
            "python3", ["-c", "import time; time.sleep(10)"], dest
        )

        assert time.monotonic() - started < 2
        assert wrote is False
        assert lines == 0


class TestPrepareZip:
    def _make_zip(self, tmp_path, zip_name, pyc_files):
        """Create a zip containing fake .pyc files."""
        from zipfile import ZipFile
        src_dir = tmp_path / "src"
        src_dir.mkdir(exist_ok=True)
        zip_path = str(src_dir / zip_name)
        with ZipFile(zip_path, "w") as zf:
            for name in pyc_files:
                zf.writestr(name, b"fake pyc content")
        return str(src_dir)

    def test_extracts_files_to_decompile(self, tmp_path):
        from util.decompile import _prepare_zip
        src_dir = self._make_zip(tmp_path, "test.zip", ["mod.pyc", "sub/util.pyc"])
        dst_dir = str(tmp_path / "output")
        os.makedirs(dst_dir, exist_ok=True)

        tmp_dir, to_decompile = _prepare_zip(src_dir, "test.zip", dst_dir)
        assert len(to_decompile) == 2
        # Each entry is (src_file, dest_path)
        dest_paths = [d for _, d in to_decompile]
        assert any(d.endswith("mod.py") for d in dest_paths)
        assert any(d.endswith("util.py") for d in dest_paths)
        tmp_dir.cleanup()

    def test_removes_stale_files(self, tmp_path):
        from util.decompile import _prepare_zip
        # Create a zip with only one file
        src_dir = self._make_zip(tmp_path, "test.zip", ["kept.pyc"])
        dst_dir = str(tmp_path / "output")
        dest_mod_dir = os.path.join(dst_dir, "test")
        os.makedirs(dest_mod_dir, exist_ok=True)

        # Place a stale .py file that has no corresponding .pyc in the zip
        stale_path = os.path.join(dest_mod_dir, "removed.py")
        with open(stale_path, "w") as f:
            f.write("# stale")

        tmp_dir, _ = _prepare_zip(src_dir, "test.zip", dst_dir)
        assert not os.path.isfile(stale_path)
        tmp_dir.cleanup()

    def test_removes_orphaned_temp_files(self, tmp_path):
        from util.decompile import _prepare_zip
        src_dir = self._make_zip(tmp_path, "test.zip", ["mod.pyc"])
        dst_dir = str(tmp_path / "output")
        dest_mod_dir = os.path.join(dst_dir, "test")
        os.makedirs(dest_mod_dir, exist_ok=True)

        # Place an orphaned temp file (non-.py extension)
        orphan = os.path.join(dest_mod_dir, "mod.py1b47pg0x")
        with open(orphan, "w") as f:
            f.write("# orphan")

        tmp_dir, _ = _prepare_zip(src_dir, "test.zip", dst_dir)
        assert not os.path.isfile(orphan)
        tmp_dir.cleanup()


class TestDecompileWorker:
    @pytest.fixture
    def _init_worker(self):
        """Set up process-module globals needed by decompile_worker."""
        from util.decompile import Stats, TotalStats, init_process
        from multiprocessing import Manager
        stats = Value(Stats, 0, 0, 0, 0)
        total = Value(TotalStats, 0, 0, 0, 0)
        mgr = Manager()
        failed = mgr.list()
        init_process(stats, total, failed)
        yield stats, total, failed
        mgr.shutdown()

    def test_writes_stub_on_total_failure(self, tmp_path, _init_worker):
        from util.decompile import decompile_worker
        stats, total, failed = _init_worker

        # Create a fake .pyc that no decompiler can handle
        src = str(tmp_path / "bad.pyc")
        with open(src, "w") as f:
            f.write("not real bytecode")
        dest = str(tmp_path / "bad.py")

        decompile_worker(src, dest)
        assert os.path.isfile(dest)
        with open(dest) as f:
            content = f.read()
        assert "Decompilation failed" in content
        assert total.fail_count == 1

    def test_deletes_existing_output_before_decompile(self, tmp_path, _init_worker):
        from util.decompile import decompile_worker

        src = str(tmp_path / "test.pyc")
        with open(src, "w") as f:
            f.write("not real bytecode")
        dest = str(tmp_path / "test.py")
        # Write pre-existing content
        with open(dest, "w") as f:
            f.write("# old stale content from previous run\nold_var = 42\n")

        decompile_worker(src, dest)
        with open(dest) as f:
            content = f.read()
        # Old content should be gone
        assert "old stale content" not in content
        assert "old_var" not in content

    def test_header_prepended(self, tmp_path, _init_worker):
        from util.decompile import decompile_worker

        src = str(tmp_path / "test.pyc")
        with open(src, "w") as f:
            f.write("not real bytecode")
        dest = str(tmp_path / "test.py")

        decompile_worker(src, dest)
        with open(dest) as f:
            first_line = f.readline()
        # Should start with a decompiler header comment
        assert first_line.startswith("# Decompil")

    def test_syntax_invalid_output_uses_next_fallback(
        self, tmp_path, _init_worker, monkeypatch
    ):
        import util.decompile as decompile_mod

        src = str(tmp_path / "test.pyc")
        with open(src, "wb") as file:
            file.write(b"fake bytecode")
        dest = str(tmp_path / "test.py")

        def invalid_stdout_decompile(cmd, args, dest_path):
            with open(dest_path, "w", encoding="utf-8") as file:
                file.write("if value BAD 0:\n    pass\n")
            return True, CompletedProcess([cmd], 0, "", "")

        def valid_exec_cli(package, args):
            output_path = args[3]
            with open(output_path, "w", encoding="utf-8") as file:
                file.write("value = 42\n")
            return True, CompletedProcess([package], 0, "", "")

        monkeypatch.setattr(
            decompile_mod, "stdout_decompile", invalid_stdout_decompile
        )
        monkeypatch.setattr(decompile_mod, "exec_cli", valid_exec_cli)

        decompile_mod.decompile_worker(src, dest)

        with open(dest, encoding="utf-8") as file:
            content = file.read()
        assert content.startswith("# Decompiled with decompyle3\n")
        assert "value = 42" in content
        assert "BAD" not in content


class TestDecompileZips:
    def test_accepts_string_src_dir(self, tmp_path):
        from util.decompile import decompile_zips
        src_dir = str(tmp_path / "src")
        dst_dir = str(tmp_path / "output")
        os.makedirs(src_dir, exist_ok=True)
        os.makedirs(dst_dir, exist_ok=True)
        # Empty directory — should return without error
        decompile_zips(src_dir, dst_dir)

    def test_accepts_list_src_dirs(self, tmp_path):
        from util.decompile import decompile_zips
        dir_a = str(tmp_path / "a")
        dir_b = str(tmp_path / "b")
        dst = str(tmp_path / "output")
        os.makedirs(dir_a, exist_ok=True)
        os.makedirs(dir_b, exist_ok=True)
        os.makedirs(dst, exist_ok=True)
        # Empty directories — should return without error
        decompile_zips([dir_a, dir_b], dst)


class TestDecompileModFolder:
    def test_creates_named_output_manifest_and_python_folder(self, tmp_path, monkeypatch):
        import util.decompile as decompile_mod

        mod_name = "SimRealist_-_SimNationalBank_3.2.1.1"
        mod_folder = tmp_path / "Mods" / mod_name
        nested = mod_folder / "Scripts"
        nested.mkdir(parents=True)
        script_archive = nested / "bank_core.ts4script"
        package_file = mod_folder / "bank_data.package"
        script_archive.write_bytes(b"archive")
        package_file.write_bytes(b"package")

        output_root = tmp_path / "decompile" / "output"
        old_output = output_root / "mods" / mod_name
        old_output.mkdir(parents=True)
        stale_file = old_output / "stale.py"
        stale_file.write_text("stale")

        calls = []
        monkeypatch.setattr(
            decompile_mod,
            "decompile_zips",
            lambda src, dst: calls.append((src, dst)),
        )

        result = decompile_mod.decompile_mod_folder(
            str(mod_folder), str(output_root)
        )

        expected_output = output_root / "mods" / mod_name
        expected_python = expected_output / "python"
        assert result == str(expected_output)
        assert not stale_file.exists()
        assert expected_python.is_dir()
        assert calls == [(str(mod_folder.resolve()), str(expected_python))]

        with open(str(expected_output / "manifest.json"), encoding="utf-8") as file:
            manifest = json.load(file)
        assert manifest == {
            "format_version": 1,
            "mod_name": mod_name,
            "source_folder": str(mod_folder.resolve()),
            "script_archives": [os.path.join("Scripts", "bank_core.ts4script")],
            "package_files": ["bank_data.package"],
            "python_output": "python",
        }

    def test_missing_mod_folder_is_rejected(self, tmp_path):
        from util.decompile import decompile_mod_folder

        with pytest.raises(NotADirectoryError):
            decompile_mod_folder(
                str(tmp_path / "missing"), str(tmp_path / "output")
            )

    def test_no_script_archive_preserves_existing_output(self, tmp_path):
        from util.decompile import decompile_mod_folder

        mod_folder = tmp_path / "Mods" / "PackageOnlyMod"
        mod_folder.mkdir(parents=True)
        (mod_folder / "content.package").write_bytes(b"package")

        output_root = tmp_path / "decompile" / "output"
        existing_output = output_root / "mods" / mod_folder.name
        existing_output.mkdir(parents=True)
        sentinel = existing_output / "keep.txt"
        sentinel.write_text("keep")

        with pytest.raises(FileNotFoundError, match="script archive"):
            decompile_mod_folder(str(mod_folder), str(output_root))

        assert sentinel.read_text() == "keep"
