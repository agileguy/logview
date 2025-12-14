"""Tests for the log discovery service."""

from __future__ import annotations

from pathlib import Path

from logview.adapters.discovery import (
    discover_logs,
    format_size,
)


class TestDiscoverLogs:
    """Tests for discover_logs function."""

    def test_discovers_log_files(self, tmp_path: Path) -> None:
        """Test that log files are discovered."""
        # Create test log files
        log1 = tmp_path / "app.log"
        log1.write_text("log content\n")

        log2 = tmp_path / "error.log"
        log2.write_text("error content\n")

        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            allowed_directories=[str(tmp_path)],
        )

        paths = [d.path for d in discovered]
        assert log1 in paths
        assert log2 in paths

    def test_discovers_files_in_subdirectories(self, tmp_path: Path) -> None:
        """Test that files in subdirectories are discovered."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        log_file = subdir / "app.log"
        log_file.write_text("content\n")

        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            allowed_directories=[str(tmp_path)],
        )

        paths = [d.path for d in discovered]
        assert log_file in paths

    def test_respects_max_depth(self, tmp_path: Path) -> None:
        """Test that max_depth is respected."""
        # Create nested directories
        deep_dir = tmp_path / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)

        shallow_log = tmp_path / "a" / "shallow.log"
        shallow_log.write_text("content\n")

        deep_log = deep_dir / "deep.log"
        deep_log.write_text("content\n")

        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            max_depth=2,
            allowed_directories=[str(tmp_path)],
        )

        paths = [d.path for d in discovered]
        assert shallow_log in paths
        assert deep_log not in paths

    def test_skips_compressed_files(self, tmp_path: Path) -> None:
        """Test that compressed files are skipped."""
        gz_file = tmp_path / "app.log.gz"
        gz_file.write_bytes(b"\x1f\x8b")  # gzip magic bytes

        bz2_file = tmp_path / "app.log.bz2"
        bz2_file.write_bytes(b"BZ")

        regular_file = tmp_path / "app.log"
        regular_file.write_text("content\n")

        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            allowed_directories=[str(tmp_path)],
        )

        paths = [d.path for d in discovered]
        assert regular_file in paths
        assert gz_file not in paths
        assert bz2_file not in paths

    def test_skips_rotated_logs(self, tmp_path: Path) -> None:
        """Test that rotated logs (numbered) are skipped."""
        base_log = tmp_path / "syslog"
        base_log.write_text("content\n")

        rotated1 = tmp_path / "syslog.1"
        rotated1.write_text("old content\n")

        rotated2 = tmp_path / "syslog.2"
        rotated2.write_text("older content\n")

        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            allowed_directories=[str(tmp_path)],
        )

        paths = [d.path for d in discovered]
        assert base_log in paths
        assert rotated1 not in paths
        assert rotated2 not in paths

    def test_skips_hidden_files(self, tmp_path: Path) -> None:
        """Test that hidden files are skipped."""
        hidden_file = tmp_path / ".hidden.log"
        hidden_file.write_text("content\n")

        regular_file = tmp_path / "regular.log"
        regular_file.write_text("content\n")

        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            allowed_directories=[str(tmp_path)],
        )

        paths = [d.path for d in discovered]
        assert regular_file in paths
        assert hidden_file not in paths

    def test_skips_hidden_directories(self, tmp_path: Path) -> None:
        """Test that hidden directories are skipped."""
        hidden_dir = tmp_path / ".hidden"
        hidden_dir.mkdir()

        hidden_log = hidden_dir / "app.log"
        hidden_log.write_text("content\n")

        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            allowed_directories=[str(tmp_path)],
        )

        paths = [d.path for d in discovered]
        assert hidden_log not in paths

    def test_skips_binary_files(self, tmp_path: Path) -> None:
        """Test that binary files are skipped."""
        binary_file = tmp_path / "binary.log"
        binary_file.write_bytes(b"\x00\x01\x02\x03" * 100)

        text_file = tmp_path / "text.log"
        text_file.write_text("regular text content\n")

        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            allowed_directories=[str(tmp_path)],
        )

        paths = [d.path for d in discovered]
        assert text_file in paths
        assert binary_file not in paths

    def test_respects_allowed_directories(self, tmp_path: Path) -> None:
        """Test that only allowed directories are searched."""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        disallowed_dir = tmp_path / "disallowed"
        disallowed_dir.mkdir()

        allowed_log = allowed_dir / "app.log"
        allowed_log.write_text("content\n")

        disallowed_log = disallowed_dir / "app.log"
        disallowed_log.write_text("content\n")

        discovered = discover_logs(
            search_paths=[str(allowed_dir), str(disallowed_dir)],
            allowed_directories=[str(allowed_dir)],
        )

        paths = [d.path for d in discovered]
        assert allowed_log in paths
        assert disallowed_log not in paths

    def test_returns_file_size(self, tmp_path: Path) -> None:
        """Test that file size is returned."""
        log_file = tmp_path / "app.log"
        log_file.write_text("12345678901234567890")  # 20 bytes

        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            allowed_directories=[str(tmp_path)],
        )

        assert len(discovered) == 1
        assert discovered[0].size_bytes == 20

    def test_returns_readable_flag(self, tmp_path: Path) -> None:
        """Test that readable flag is returned."""
        log_file = tmp_path / "app.log"
        log_file.write_text("content\n")

        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            allowed_directories=[str(tmp_path)],
        )

        assert len(discovered) == 1
        assert discovered[0].readable is True

    def test_generates_context_name(self, tmp_path: Path) -> None:
        """Test that context names are generated."""
        subdir = tmp_path / "myapp"
        subdir.mkdir()

        log_file = subdir / "server.log"
        log_file.write_text("content\n")

        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            allowed_directories=[str(tmp_path)],
        )

        log_entry = next(d for d in discovered if d.path == log_file)
        assert "server" in log_entry.name or "myapp" in log_entry.name

    def test_handles_nonexistent_search_path(self, tmp_path: Path) -> None:
        """Test that nonexistent search paths are handled gracefully."""
        discovered = discover_logs(
            search_paths=[str(tmp_path / "nonexistent")],
            allowed_directories=[str(tmp_path)],
        )

        assert discovered == []

    def test_handles_empty_directory(self, tmp_path: Path) -> None:
        """Test that empty directories are handled."""
        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            allowed_directories=[str(tmp_path)],
        )

        assert discovered == []

    def test_deduplicates_symlinked_files(self, tmp_path: Path) -> None:
        """Test that symlinked files are deduplicated."""
        log_file = tmp_path / "app.log"
        log_file.write_text("content\n")

        symlink = tmp_path / "app_link.log"
        symlink.symlink_to(log_file)

        discovered = discover_logs(
            search_paths=[str(tmp_path)],
            allowed_directories=[str(tmp_path)],
        )

        # Should only find one (the resolved path)
        assert len(discovered) == 1


class TestFormatSize:
    """Tests for format_size function."""

    def test_formats_bytes(self) -> None:
        """Test formatting bytes."""
        assert format_size(0) == "0 B"
        assert format_size(100) == "100 B"
        assert format_size(1023) == "1023 B"

    def test_formats_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        assert format_size(1024) == "1.0 KB"
        assert format_size(1536) == "1.5 KB"
        assert format_size(10240) == "10.0 KB"

    def test_formats_megabytes(self) -> None:
        """Test formatting megabytes."""
        assert format_size(1024 * 1024) == "1.0 MB"
        assert format_size(1024 * 1024 * 5) == "5.0 MB"

    def test_formats_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        assert format_size(1024 * 1024 * 1024) == "1.0 GB"
        assert format_size(1024 * 1024 * 1024 * 2) == "2.0 GB"
