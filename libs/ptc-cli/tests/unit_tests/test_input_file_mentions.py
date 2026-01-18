"""Unit tests for file mention parsing."""


from ptc_cli.input.file_mentions import parse_file_mentions


class TestParseFileMentions:
    """Test file mention parsing."""

    def test_single_file_mention(self):
        """Test parsing a single @file mention."""
        text = "Check out @test.py for details"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 1
        assert paths[0] == "test.py"

    def test_multiple_file_mentions(self):
        """Test parsing multiple @file mentions."""
        text = "Compare @file1.py with @file2.py and @file3.py"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 3
        assert paths == ["file1.py", "file2.py", "file3.py"]

    def test_no_mentions_returns_empty_list(self):
        """Test text without mentions returns empty list."""
        text = "This has no file mentions"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 0
        assert paths == []

    def test_path_with_directory(self):
        """Test @mention with directory path."""
        text = "Look at @src/main.py"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 1
        assert paths[0] == "src/main.py"

    def test_escaped_spaces_in_path(self):
        """Test @mention with escaped spaces."""
        text = "Check @my\\ file.py"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 1
        assert paths[0] == "my file.py"  # Spaces unescaped

    def test_mention_at_start_of_text(self):
        """Test @mention at the start of text."""
        text = "@file.py is important"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 1
        assert paths[0] == "file.py"

    def test_mention_at_end_of_text(self):
        """Test @mention at the end of text."""
        text = "Check out @file.py"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 1
        assert paths[0] == "file.py"

    def test_mention_with_extension(self):
        """Test @mention with various file extensions."""
        text = "@test.py @data.json @config.yaml @doc.md"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 4
        assert paths == ["test.py", "data.json", "config.yaml", "doc.md"]

    def test_mention_stops_at_whitespace(self):
        """Test @mention stops at whitespace."""
        text = "@file.py and more text"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 1
        assert paths[0] == "file.py"

    def test_mention_stops_at_at_sign(self):
        """Test @mention stops at another @ sign."""
        text = "@file1.py@file2.py"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 2
        assert paths == ["file1.py", "file2.py"]

    def test_complex_path_with_dots(self):
        """Test @mention with complex paths containing dots."""
        text = "@src/utils/helper.test.py"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 1
        assert paths[0] == "src/utils/helper.test.py"

    def test_mention_with_underscores_and_hyphens(self):
        """Test @mention with underscores and hyphens."""
        text = "@my_file-name.py"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 1
        assert paths[0] == "my_file-name.py"

    def test_empty_text(self):
        """Test empty text returns empty list."""
        text = ""
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 0
        assert paths == []

    def test_at_sign_only(self):
        """Test @ sign only without path."""
        text = "Just an @ sign"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        # Should extract empty string or handle gracefully
        assert len(paths) <= 1

    def test_multiple_escaped_spaces(self):
        """Test multiple escaped spaces in path."""
        text = "@my\\ complex\\ file\\ name.py"
        result_text, paths = parse_file_mentions(text)

        assert result_text == text
        assert len(paths) == 1
        assert paths[0] == "my complex file name.py"
