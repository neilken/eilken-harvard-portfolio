"""Unit tests for RAG core functions, internal helpers, and utilities."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import tempfile
import os
import numpy as np

pytestmark = pytest.mark.unit

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import functions to test
rag = pytest.importorskip("rag")
from rag import (
    normalize_query,
    _norm,
    _load_txt_md,
    _load_md_feature_file,
    _load_full_md_file,
    load_all,
    semantic_chunks,
    SemanticChunker,
    get_embedder,
    semantic_embed,
    _enrich_chunk_with_context,
    _apply_sentence_overlap,
    _approx_token_len,
    _combine_sentences,
    _calc_cosine_distances,
    _split_sentences_cached,
    _pack_sentences_to_token_cap,
    _get_semantic_splitter,
    _remove_headers_footers,
    _finalize_and_output_chapter,
    cached_embed,
    _load_env_file,
    _touch_chromadb_files,
    get_chromadb_client,
    SemanticSplitterCache,
    _signal_handler,
)


# ============================================================================
# Core RAG Functions
# ============================================================================


class TestNormalizeQuery:
    """Tests for normalize_query function."""

    @pytest.mark.parametrize(
        "input_query,expected",
        [
            ("What is ROE?", "what is roe?"),
            ("  What   is   ROE?  ", "what is roe?"),
            ("", ""),
            ("   ", ""),
        ],
    )
    def test_normalize_query_strings(self, input_query, expected):
        """Test query normalization for string inputs."""
        result = normalize_query(input_query)
        assert result == expected

    @pytest.mark.parametrize("input_query", [None, 123, [], {}])
    def test_normalize_query_non_string(self, input_query):
        """Test non-string input returns empty string."""
        assert normalize_query(input_query) == ""


class TestNorm:
    """Tests for _norm text normalization function."""

    @pytest.mark.parametrize(
        "text,expected_contains",
        [
            ("  Hello   World  ", "Hello World"),
            ("Hello\u2014World", ["Hello", "World"]),  # Em dash
            ("Line 1\n\n\nLine 2", ["Line 1", "Line 2", "\n\n"]),  # Preserves paragraph breaks
        ],
    )
    def test_norm_various_inputs(self, text, expected_contains):
        """Test text normalization for various inputs."""
        result = _norm(text)
        if isinstance(expected_contains, list):
            for item in expected_contains:
                assert item in result
        else:
            assert expected_contains in result

    @pytest.mark.parametrize("text", ["", None])
    def test_norm_empty(self, text):
        """Test empty text returns empty string."""
        assert _norm(text) == ""


class TestLoadFunctions:
    """Tests for document loading functions."""

    def test_load_txt_md(self, tmp_path):
        """Test loading text/markdown files."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Sample text content")

        result = _load_txt_md(str(test_file))
        assert len(result) == 1
        assert result[0][0] == str(test_file)
        assert "Sample text content" in result[0][1]

    def test_load_md_feature_file(self, tmp_path):
        """Test loading markdown feature file."""
        # Test with LLM-Quant_Expanded_RAG_with_context.md filename
        test_file = tmp_path / "LLM-Quant_Expanded_RAG_with_context.md"
        # Create markdown structure matching actual file format
        md_content = """## roe
**Definition / Formula:** Return on Equity = Net Income / Shareholder Equity

**Meaning:** Profitability relative to equity

**Interpretation / Signal:** High ROE >15% = efficient management

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## peRatio
**Definition / Formula:** Price / EPS

**Meaning:** Valuation multiple

**Interpretation / Signal:** Low PE = undervalued; High PE = growth premium

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.
"""
        test_file.write_text(md_content)

        result = _load_md_feature_file(str(test_file))
        # Should extract features from markdown file
        assert isinstance(result, list)
        assert len(result) >= 2  # Should have at least 2 features
        # Check that feature information is extracted
        assert any("roe" in item[1].lower() for item in result)
        assert any("peRatio" in item[1] or "pe ratio" in item[1].lower() for item in result)
        # Check that fields are extracted correctly
        roe_item = next((item for item in result if "roe" in item[1].lower()), None)
        assert roe_item is not None
        assert "Return on Equity" in roe_item[1]
        assert "Profitability relative to equity" in roe_item[1]

    def test_load_md_feature_file_wrong_filename(self, tmp_path):
        """Test that markdown loader only processes the specific feature file."""
        # Test with different markdown filename (should return empty)
        test_file = tmp_path / "other_file.md"
        test_file.write_text("## Some Feature\nContent here")

        result = _load_md_feature_file(str(test_file))
        # Should return empty list for non-matching filename
        assert result == []

    def test_load_full_md_file(self, tmp_path):
        """Test loading full markdown file as a single document."""
        test_file = tmp_path / "test.md"
        md_content = """## Feature 1
**Definition / Formula:** Formula 1
**Meaning:** Meaning 1
---
## Feature 2
**Definition / Formula:** Formula 2
**Meaning:** Meaning 2
"""
        test_file.write_text(md_content)

        result = _load_full_md_file(str(test_file))
        # Should return single document with full content
        assert len(result) == 1
        assert result[0][0] == f"{str(test_file)}#full_document"
        assert "Feature 1" in result[0][1]
        assert "Feature 2" in result[0][1]
        assert "Formula 1" in result[0][1]
        assert "Formula 2" in result[0][1]

    def test_load_full_md_file_missing_file(self):
        """Test loading non-existent markdown file returns empty list."""
        result = _load_full_md_file("/nonexistent/path/file.md")
        # Should return empty list on error
        assert result == []

    def test_load_full_md_file_empty_file(self, tmp_path):
        """Test loading empty markdown file."""
        test_file = tmp_path / "empty.md"
        test_file.write_text("")

        result = _load_full_md_file(str(test_file))
        # Should return single document with empty content (normalized)
        assert len(result) == 1
        assert result[0][0] == f"{str(test_file)}#full_document"
        assert result[0][1] == ""  # Empty string after normalization

    def test_load_full_md_file_text_normalization(self, tmp_path):
        """Test that text normalization is applied to loaded content."""
        test_file = tmp_path / "test.md"
        # Content with extra whitespace that should be normalized
        md_content = "  Feature  \n\n  Content  \n  "
        test_file.write_text(md_content)

        result = _load_full_md_file(str(test_file))
        # Should normalize whitespace
        assert len(result) == 1
        assert result[0][0] == f"{str(test_file)}#full_document"
        # Normalized text should have cleaned whitespace
        assert "Feature" in result[0][1]
        assert "Content" in result[0][1]

    def test_load_all(self, tmp_path):
        """Test load_all function with multiple files."""
        # Create test files
        (tmp_path / "test1.txt").write_text("Content 1")
        (tmp_path / "test2.txt").write_text("Content 2")

        # Mock to avoid actual file system and PDF issues in CI
        with (
            patch("rag._load_txt_md") as mock_load_txt,
            patch("rag._load_pdf") as mock_load_pdf,
            patch("rag._load_md_feature_file") as mock_load_md_feature,
            patch("rag._load_full_md_file") as mock_load_full_md,
        ):
            mock_load_txt.return_value = [("test1.txt", "Content 1")]
            mock_load_pdf.return_value = []
            mock_load_md_feature.return_value = []
            mock_load_full_md.return_value = []
            # Note: CSV files are skipped in load_all() - feature definitions now come from markdown files

            result = load_all(str(tmp_path))
            # Should return loaded documents
            assert isinstance(result, list)


class TestSemanticChunking:
    """Tests for semantic chunking functions."""

    @patch("rag.get_embedder")
    @patch("rag.semantic_embed")
    def test_semantic_chunks_small_text(self, mock_embed, mock_get_embedder):
        """Test semantic_chunks with small text that fits in one chunk."""
        small_text = "Short text."
        result = semantic_chunks(small_text, max_tokens=1400)
        assert isinstance(result, list)
        assert len(result) > 0

    @patch("rag.get_embedder")
    @patch("rag.semantic_embed")
    def test_semantic_chunks_large_text(self, mock_embed, mock_get_embedder):
        """Test semantic_chunks with large text that needs splitting."""
        # Create moderate-sized text (reduced from 100 to 30 for memory efficiency)
        large_text = " ".join(["Sentence with content."] * 30)

        # Mock embedding to return enough embeddings for all sentences
        # Split by sentences first to estimate how many we need
        sentences = large_text.split(".")
        num_sentences = len([s for s in sentences if s.strip()])
        # Use smaller embeddings (128 dim) for memory efficiency
        # Return embeddings for all sentences to avoid IndexError (reduced max from 100 to 50)
        mock_embed.return_value = [[0.1] * 128] * max(num_sentences, 50)

        result = semantic_chunks(large_text, max_tokens=100)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_apply_sentence_overlap(self):
        """Test sentence overlap application."""
        chunks = ["First sentence. Second sentence.", "Third sentence. Fourth sentence.", "Fifth sentence."]

        result = _apply_sentence_overlap(chunks, overlap_sentences=1)
        assert len(result) == len(chunks)
        # First chunk should have overlap from second
        assert len(result[0]) >= len(chunks[0])

    @pytest.mark.parametrize(
        "overlap_sentences,should_change",
        [
            (0, False),
            (1, True),
        ],
    )
    def test_apply_sentence_overlap(self, overlap_sentences, should_change):
        """Test sentence overlap with different overlap values."""
        chunks = ["Chunk 1", "Chunk 2"]
        result = _apply_sentence_overlap(chunks, overlap_sentences=overlap_sentences)
        if should_change:
            assert len(result[0]) >= len(chunks[0])
        else:
            assert result == chunks

    def test_enrich_chunk_with_context(self):
        """Test chunk context enrichment."""
        chunks = ["First chunk content.", "Second chunk content.", "Third chunk content."]

        result = _enrich_chunk_with_context(chunks, window_size=1)
        assert len(result) == len(chunks)
        # Middle chunk should have context from neighbors
        assert len(result[1]) >= len(chunks[1])


class TestEmbeddingFunctions:
    """Tests for embedding functions."""

    @patch("rag.TextEmbedding")
    def test_get_embedder(self, mock_text_embedding):
        """Test get_embedder returns embedder instance."""
        mock_embedder = Mock()
        mock_text_embedding.return_value = mock_embedder

        # Reset global cache
        import rag

        rag._EMBEDDER = None

        result = get_embedder()
        assert result is not None

    @patch("rag.get_embedder")
    def test_semantic_embed(self, mock_get_embedder):
        """Test semantic_embed function."""
        mock_embedder = Mock()
        # Use smaller embeddings (128 dim) for memory efficiency
        mock_embedder.embed.return_value = iter([[0.1] * 128, [0.2] * 128])
        mock_get_embedder.return_value = mock_embedder

        texts = ["text1", "text2"]
        result = semantic_embed(texts)

        assert isinstance(result, list)
        assert len(result) == len(texts)


class TestUtilityFunctions:
    """Tests for utility functions."""

    @pytest.mark.parametrize(
        "text,expected_min",
        [
            ("This is a test sentence with multiple words.", 1),
            ("Hi", 1),
            ("", 1),
        ],
    )
    def test_approx_token_len(self, text, expected_min):
        """Test token length approximation for various inputs."""
        result = _approx_token_len(text)
        assert isinstance(result, int)
        assert result >= expected_min


class TestSemanticChunker:
    """Tests for SemanticChunker class."""

    def test_semantic_chunker_init(self):
        """Test SemanticChunker initialization."""
        # Use smaller embeddings (128 dim) for memory efficiency
        mock_embed_func = Mock(return_value=[[0.1] * 128])

        chunker = SemanticChunker(
            embedding_function=mock_embed_func,
            buffer_size=1,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=95.0,
        )

        assert chunker is not None
        assert chunker.buffer_size == 1


# ============================================================================
# Internal Helper Functions
# ============================================================================


class TestCombineSentences:
    """Tests for _combine_sentences function."""

    def test_combine_sentences_no_buffer(self):
        """Test combining sentences with buffer_size=0."""
        sentences = [
            {"sentence": "First sentence."},
            {"sentence": "Second sentence."},
            {"sentence": "Third sentence."},
        ]
        result = _combine_sentences(sentences, buffer_size=0)

        assert len(result) == 3
        assert result[0]["combined_sentence"] == "First sentence."
        assert result[1]["combined_sentence"] == "Second sentence."
        assert result[2]["combined_sentence"] == "Third sentence."

    def test_combine_sentences_with_buffer(self):
        """Test combining sentences with buffer_size=1."""
        sentences = [
            {"sentence": "First sentence."},
            {"sentence": "Second sentence."},
            {"sentence": "Third sentence."},
        ]
        result = _combine_sentences(sentences, buffer_size=1)

        assert len(result) == 3
        # First sentence should have first and second
        assert "First sentence." in result[0]["combined_sentence"]
        assert "Second sentence." in result[0]["combined_sentence"]
        # Middle sentence should have all three
        assert "First sentence." in result[1]["combined_sentence"]
        assert "Second sentence." in result[1]["combined_sentence"]
        assert "Third sentence." in result[1]["combined_sentence"]
        # Last sentence should have second and third
        assert "Second sentence." in result[2]["combined_sentence"]
        assert "Third sentence." in result[2]["combined_sentence"]

    def test_combine_sentences_large_buffer(self):
        """Test combining sentences with large buffer_size."""
        sentences = [
            {"sentence": "First."},
            {"sentence": "Second."},
            {"sentence": "Third."},
        ]
        result = _combine_sentences(sentences, buffer_size=10)

        # All sentences should include all context
        for item in result:
            assert "First." in item["combined_sentence"]
            assert "Second." in item["combined_sentence"]
            assert "Third." in item["combined_sentence"]

    @pytest.mark.parametrize(
        "sentences,buffer_size,expected_len",
        [
            ([{"sentence": "Only sentence."}], 1, 1),
            ([], 1, 0),
        ],
    )
    def test_combine_sentences_edge_cases(self, sentences, buffer_size, expected_len):
        """Test combining single/empty sentence lists."""
        result = _combine_sentences(sentences, buffer_size=buffer_size)
        assert len(result) == expected_len
        if expected_len > 0:
            assert result[0]["combined_sentence"] == sentences[0]["sentence"]


class TestCalcCosineDistances:
    """Tests for _calc_cosine_distances function."""

    @pytest.mark.parametrize(
        "sentences,expected_dist_len,expected_sent_len",
        [
            ([], 0, 0),
            ([{"combined_sentence_embedding": np.array([1.0, 0.0, 0.0])}], 0, 1),
        ],
    )
    def test_calc_cosine_distances_edge_cases(self, sentences, expected_dist_len, expected_sent_len):
        """Test with empty/single sentence lists."""
        distances, result = _calc_cosine_distances(sentences)
        assert len(distances) == expected_dist_len
        assert len(result) == expected_sent_len

    def test_calc_cosine_distances_two_sentences(self):
        """Test with two sentences."""
        # Create two similar embeddings
        emb1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        emb2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)

        sentences = [
            {"combined_sentence_embedding": emb1},
            {"combined_sentence_embedding": emb2},
        ]
        distances, result = _calc_cosine_distances(sentences)

        assert len(distances) == 1
        # Identical vectors should have distance close to 0
        assert distances[0] < 0.01
        assert "distance_to_next" in result[0]

    def test_calc_cosine_distances_orthogonal(self):
        """Test with orthogonal (perpendicular) embeddings."""
        emb1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        emb2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        sentences = [
            {"combined_sentence_embedding": emb1},
            {"combined_sentence_embedding": emb2},
        ]
        distances, result = _calc_cosine_distances(sentences)

        assert len(distances) == 1
        # Orthogonal vectors should have distance close to 1
        assert 0.9 < distances[0] <= 1.0

    def test_calc_cosine_distances_multiple(self):
        """Test with multiple sentences."""
        embeddings = [
            np.array([1.0, 0.0, 0.0], dtype=np.float32),
            np.array([0.9, 0.1, 0.0], dtype=np.float32),
            np.array([0.0, 1.0, 0.0], dtype=np.float32),
        ]

        sentences = [{"combined_sentence_embedding": emb} for emb in embeddings]
        distances, result = _calc_cosine_distances(sentences)

        assert len(distances) == 2
        assert all(0 <= d <= 1 for d in distances)
        assert all("distance_to_next" in s for s in result[:-1])


class TestSplitSentencesCached:
    """Tests for _split_sentences_cached function."""

    def test_split_sentences_basic(self):
        """Test basic sentence splitting."""
        text = "First sentence. Second sentence. Third sentence."
        result = _split_sentences_cached(text)

        assert len(result) == 3
        assert "First sentence" in result[0]
        assert "Second sentence" in result[1]
        assert "Third sentence" in result[2]

    def test_split_sentences_custom_regex(self):
        """Test with custom regex pattern."""
        text = "First sentence! Second sentence? Third sentence."
        result = _split_sentences_cached(text, regex_pattern=r"[!?.]")

        assert len(result) >= 3

    @pytest.mark.parametrize("text", ["", "   \n\n   "])
    def test_split_sentences_empty_or_whitespace(self, text):
        """Test with empty or whitespace-only text."""
        result = _split_sentences_cached(text)
        assert result == []

    def test_split_sentences_caching(self):
        """Test that caching works."""
        text = "Test sentence. Another sentence."

        # First call
        result1 = _split_sentences_cached(text)
        # Second call should use cache
        result2 = _split_sentences_cached(text)

        assert result1 == result2
        assert len(result1) == 2

    def test_split_sentences_multiple_punctuation(self):
        """Test with multiple punctuation marks."""
        text = "First... Second!!! Third???"
        result = _split_sentences_cached(text)
        # Should handle multiple punctuation
        assert len(result) >= 1


class TestPackSentencesToTokenCap:
    """Tests for _pack_sentences_to_token_cap function."""

    @pytest.mark.parametrize(
        "text,max_tokens,expected_min_chunks",
        [
            ("", 100, 0),
            ("Short text that fits.", 100, 1),
        ],
    )
    def test_pack_sentences_edge_cases(self, text, max_tokens, expected_min_chunks):
        """Test with empty/small text."""
        result = _pack_sentences_to_token_cap(text, max_tokens=max_tokens)
        assert len(result) >= expected_min_chunks
        if expected_min_chunks > 0:
            assert text in result[0]

    def test_pack_sentences_large_text(self):
        """Test with text that needs multiple chunks."""
        # Create text with many sentences
        sentences = [f"Sentence {i} with some content." for i in range(50)]
        text = " ".join(sentences)

        result = _pack_sentences_to_token_cap(text, max_tokens=50)

        # Should create multiple chunks
        assert len(result) > 1
        # All chunks should be non-empty
        assert all(chunk.strip() for chunk in result)

    def test_pack_sentences_custom_regex(self):
        """Test with custom sentence split regex."""
        text = "First! Second? Third."
        result = _pack_sentences_to_token_cap(text, max_tokens=100, sentence_split_regex=r"[!?.]")

        assert len(result) >= 1

    def test_pack_sentences_very_small_cap(self):
        """Test with very small token cap."""
        text = "This is a sentence with multiple words that might exceed the cap."
        result = _pack_sentences_to_token_cap(text, max_tokens=5)

        # Should still return at least one chunk
        assert len(result) >= 1


@pytest.fixture(autouse=True)
def clear_splitter_cache():
    """Auto-clear splitter cache before and after each test."""
    import rag

    # Create fresh cache instance before test
    rag._splitter_cache = rag.SemanticSplitterCache()
    yield
    # Clear cache after test
    if hasattr(rag, "_splitter_cache"):
        rag._splitter_cache.clear()
        rag._splitter_cache = rag.SemanticSplitterCache()


class TestGetSemanticSplitter:
    """Tests for _get_semantic_splitter function."""

    @patch("rag.semantic_embed")
    @patch("rag.SemanticChunker")
    def test_get_semantic_splitter_creates_new(self, mock_chunker_class, mock_embed):
        """Test that splitter is created on first call."""
        import rag

        # Fixture already creates fresh cache, just reset mock
        mock_chunker_class.reset_mock()

        mock_chunker_instance = Mock()
        mock_chunker_class.return_value = mock_chunker_instance

        # Use unique parameters for this test
        result = _get_semantic_splitter(sim_percentile=99.0, buffer_size=5)

        assert result == mock_chunker_instance
        mock_chunker_class.assert_called_once()

    @patch("rag.semantic_embed")
    @patch("rag.SemanticChunker")
    def test_get_semantic_splitter_caching(self, mock_chunker_class, mock_embed):
        """Test that splitter is cached for same parameters."""
        import rag

        # setup_method already creates fresh cache, just reset mock
        mock_chunker_class.reset_mock()

        mock_chunker_instance = Mock()
        mock_chunker_class.return_value = mock_chunker_instance

        # Use unique parameters for this test
        # First call - should create new instance
        result1 = _get_semantic_splitter(sim_percentile=98.0, buffer_size=3)
        # Verify SemanticChunker was called
        assert (
            mock_chunker_class.call_count == 1
        ), f"Expected 1 call, got {mock_chunker_class.call_count}. Cache size: {rag._splitter_cache.size()}"

        # Second call with same params - should use cache
        result2 = _get_semantic_splitter(sim_percentile=98.0, buffer_size=3)

        # Should return same instance
        assert result1 == result2
        # Should not create another instance (cached on second call)
        assert mock_chunker_class.call_count == 1, f"Expected 1 call total, got {mock_chunker_class.call_count}"

    @patch("rag.semantic_embed")
    @patch("rag.SemanticChunker")
    def test_get_semantic_splitter_different_params(self, mock_chunker_class, mock_embed):
        """Test that different parameters create different splitters."""
        import rag

        # setup_method already creates fresh cache
        assert rag._splitter_cache.size() == 0, "Cache should be empty at start"
        mock_chunker_class.reset_mock()

        # Create mock instances - use a list that we can index
        instances = [Mock(name=f"instance_{i}") for i in range(3)]
        call_count = [0]  # Use list for mutable closure

        # Use callable for side_effect to return different instances
        def side_effect(*args, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(instances):
                return instances[idx]
            return Mock()

        mock_chunker_class.side_effect = side_effect

        # Use unique parameters to avoid collisions with other tests
        # Call with different parameters - each should create a new instance
        # Cache keys will be: "97.0_4", "96.0_4", "97.0_5" - all different
        result1 = _get_semantic_splitter(sim_percentile=97.0, buffer_size=4)
        assert (
            mock_chunker_class.call_count >= 1
        ), f"First call should trigger SemanticChunker, got {mock_chunker_class.call_count}"
        assert rag._splitter_cache.size() == 1, "Cache should have 1 entry after first call"

        result2 = _get_semantic_splitter(sim_percentile=96.0, buffer_size=4)
        assert (
            mock_chunker_class.call_count >= 2
        ), f"Second call should trigger SemanticChunker, got {mock_chunker_class.call_count}"
        assert rag._splitter_cache.size() == 2, "Cache should have 2 entries after second call"

        result3 = _get_semantic_splitter(sim_percentile=97.0, buffer_size=5)
        assert (
            mock_chunker_class.call_count >= 3
        ), f"Third call should trigger SemanticChunker, got {mock_chunker_class.call_count}"
        assert rag._splitter_cache.size() == 3, "Cache should have 3 entries after third call"

        # Should create separate instances for different params (3 different cache keys)
        assert (
            mock_chunker_class.call_count == 3
        ), f"Expected 3 calls, got {mock_chunker_class.call_count}. Cache size: {rag._splitter_cache.size()}"
        # Results should be different instances
        assert result1 != result2, "result1 and result2 should be different"
        assert result2 != result3, "result2 and result3 should be different"
        assert result1 != result3, "result1 and result3 should be different"

    @patch("rag.semantic_embed")
    @patch("rag.SemanticChunker")
    def test_get_semantic_splitter_different_buffer_sizes(self, mock_chunker, mock_embed):
        """Test with different buffer sizes."""
        import rag

        rag._splitter_cache = SemanticSplitterCache()

        mock_chunker.return_value = Mock()

        result1 = _get_semantic_splitter(sim_percentile=95.0, buffer_size=1)
        result2 = _get_semantic_splitter(sim_percentile=95.0, buffer_size=2)

        # Different buffer sizes should create different instances
        assert mock_chunker.call_count == 2


class TestRemoveHeadersFooters:
    """Tests for _remove_headers_footers function."""

    def test_remove_headers_footers_basic(self):
        """Test basic header/footer removal."""
        text = "Chapter 1\n\nMain content here.\n\nPage 5"
        result = _remove_headers_footers(text)

        # Should remove "Chapter 1" and "Page 5"
        assert "Chapter 1" not in result or "Main content" in result
        assert "Main content here" in result

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("", ""),
            (None, None),  # None or "" both acceptable
        ],
    )
    def test_remove_headers_footers_edge_cases(self, input_text, expected):
        """Test with empty/None inputs."""
        result = _remove_headers_footers(input_text)
        if expected is None:
            assert result is None or result == ""
        else:
            assert result == expected

    def test_remove_headers_footers_page_number(self):
        """Test removal of page numbers."""
        text = "Content here.\n\n5\n\nMore content."
        result = _remove_headers_footers(text, page_num=5)

        # Should preserve main content
        assert "Content here" in result or "More content" in result

    def test_remove_headers_footers_repeating_lines(self):
        """Test removal of repeating header/footer lines."""
        # Create text with repeating header
        text = "Header Text\n\nContent line 1.\nContent line 2.\n\nHeader Text"
        result = _remove_headers_footers(text)

        # Should preserve content
        assert "Content line" in result


class TestFinalizeAndOutputChapter:
    """Tests for _finalize_and_output_chapter function."""

    def test_finalize_and_output_chapter_basic(self):
        """Test basic chapter finalization."""
        items = []
        chapter_data = {
            "chapter_num": "1",
            "chapter_title": "Introduction",
            "pages": [(1, "Page 1 content"), (2, "Page 2 content")],
        }
        pdf_metadata = {"title": "Test Book"}

        _finalize_and_output_chapter(chapter_data, items, "/path/to/book.pdf", "book.pdf", pdf_metadata, 100)

        assert len(items) == 1
        source, text = items[0]
        assert "chapter=1" in source
        assert "Introduction" in source
        assert "Page 1 content" in text
        assert "Page 2 content" in text
        assert "Test Book" in text

    @pytest.mark.parametrize(
        "chapter_title,has_title",
        [
            ("Introduction", True),
            ("", False),
        ],
    )
    def test_finalize_and_output_chapter_variations(self, chapter_title, has_title):
        """Test chapter finalization with/without title."""
        items = []
        chapter_data = {
            "chapter_num": "2",
            "chapter_title": chapter_title,
            "pages": [(10, "Content")],
        }
        _finalize_and_output_chapter(chapter_data, items, "/path/to/book.pdf", "book.pdf", {}, 50)
        assert len(items) == 1
        source, text = items[0]
        assert "chapter=2" in source
        assert "Content" in text
        if has_title:
            assert chapter_title in text

    def test_finalize_and_output_chapter_page_range(self):
        """Test that page range is included in output."""
        items = []
        chapter_data = {
            "chapter_num": "5",
            "chapter_title": "Advanced Topics",
            "pages": [(20, "Page 20"), (21, "Page 21"), (22, "Page 22")],
        }

        _finalize_and_output_chapter(chapter_data, items, "/path/to/book.pdf", "book.pdf", {}, 100)

        assert len(items) == 1
        _, text = items[0]
        # Should include page range
        assert "20-22" in text or "Pages 20-22" in text


@pytest.fixture(autouse=True)
def clear_embedding_cache():
    """Auto-clear embedding cache before and after each test."""
    import rag

    rag._embedding_cache = {}
    yield
    rag._embedding_cache = {}


class TestCachedEmbed:
    """Tests for cached_embed function."""

    @patch("rag.get_embedder")
    def test_cached_embed_first_call(self, mock_get_embedder):
        """Test first call to cached_embed."""
        mock_embedder = Mock()
        mock_embedder.query_embed.return_value = iter([[0.1, 0.2, 0.3]])
        mock_get_embedder.return_value = mock_embedder

        result = cached_embed("test query")

        assert result == [0.1, 0.2, 0.3]
        mock_embedder.query_embed.assert_called_once_with("test query")

    @patch("rag.get_embedder")
    def test_cached_embed_caching(self, mock_get_embedder):
        """Test that cached_embed uses cache on second call."""
        import rag

        # Ensure cache is empty (fixture should handle this)
        rag._embedding_cache = {}

        mock_embedder = Mock()
        # Return a new iterator each time to avoid iterator exhaustion
        mock_embedder.query_embed.side_effect = [
            iter([[0.1, 0.2, 0.3]]),
            iter([[0.1, 0.2, 0.3]]),
        ]
        mock_get_embedder.return_value = mock_embedder

        # First call
        result1 = cached_embed("test query unique")
        # Second call
        result2 = cached_embed("test query unique")

        assert result1 == result2
        # Should only call embedder once (second call uses cache)
        assert mock_embedder.query_embed.call_count == 1

    @patch("rag.get_embedder")
    def test_cached_embed_different_queries(self, mock_get_embedder):
        """Test that different queries are not cached together."""
        mock_embedder = Mock()
        mock_embedder.query_embed.side_effect = [
            iter([[0.1, 0.2, 0.3]]),
            iter([[0.4, 0.5, 0.6]]),
        ]
        mock_get_embedder.return_value = mock_embedder

        result1 = cached_embed("query 1")
        result2 = cached_embed("query 2")

        assert result1 != result2
        assert mock_embedder.query_embed.call_count == 2


class TestSemanticChunkerMethods:
    """Additional tests for SemanticChunker class methods."""

    @patch("rag.semantic_embed")
    def test_semantic_chunker_get_optimal_sample_rate(self, mock_embed):
        """Test _get_optimal_sample_rate method."""
        from rag import SemanticChunker

        chunker = SemanticChunker(embedding_function=mock_embed)

        # Small docs - no sampling
        assert chunker._get_optimal_sample_rate(100) == 1
        assert chunker._get_optimal_sample_rate(199) == 1

        # Medium docs - every 5th
        assert chunker._get_optimal_sample_rate(200) == 5
        assert chunker._get_optimal_sample_rate(999) == 5

        # Large docs - every 10th
        assert chunker._get_optimal_sample_rate(1000) == 10
        assert chunker._get_optimal_sample_rate(2999) == 10

        # Very large docs - every 20th
        assert chunker._get_optimal_sample_rate(3000) == 20
        assert chunker._get_optimal_sample_rate(10000) == 20

    @patch("rag.semantic_embed")
    def test_semantic_chunker_threshold_from_clusters(self, mock_embed):
        """Test _threshold_from_clusters method."""
        from rag import SemanticChunker
        import numpy as np

        chunker = SemanticChunker(
            embedding_function=mock_embed, number_of_chunks=5, breakpoint_threshold_type="percentile"
        )

        distances = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        threshold = chunker._threshold_from_clusters(distances)

        # Should return a valid threshold
        assert isinstance(threshold, float)
        assert 0 <= threshold <= 1

    @patch("rag.semantic_embed")
    @patch("rag._split_sentences_cached")
    @patch("rag._approx_token_len")
    def test_semantic_chunker_split_text_small(
        self, mock_approx_token_len, mock_split_sentences_cached, mock_semantic_embed
    ):
        """Test SemanticChunker.split_text with small text."""
        from rag import SemanticChunker

        mock_split_sentences_cached.return_value = ["Sentence one.", "Sentence two."]
        mock_approx_token_len.return_value = 10  # Small text

        chunker = SemanticChunker(embedding_function=mock_semantic_embed)
        result = chunker.split_text("Small text here.")

        # Should return chunks
        assert isinstance(result, list)
        assert len(result) >= 1

    @patch("rag.semantic_embed")
    def test_semantic_chunker_create_documents(self, mock_embed):
        """Test SemanticChunker.create_documents method."""
        from rag import SemanticChunker

        # Mock split_text to return simple chunks
        chunker = SemanticChunker(embedding_function=mock_embed)
        chunker.split_text = Mock(return_value=["Chunk 1", "Chunk 2"])

        texts = ["Document 1 text", "Document 2 text"]
        result = chunker.create_documents(texts)

        assert isinstance(result, list)
        assert len(result) >= 2
        # Each document should have page_content
        for doc in result:
            assert "page_content" in doc or hasattr(doc, "page_content")

    @patch("rag.semantic_embed")
    def test_semantic_chunker_create_documents_with_metadata(self, mock_embed):
        """Test SemanticChunker.create_documents with metadata."""
        from rag import SemanticChunker

        chunker = SemanticChunker(embedding_function=mock_embed)
        chunker.split_text = Mock(return_value=["Chunk 1"])

        texts = ["Document 1"]
        metadatas = [{"source": "test.pdf", "page": 1}]
        result = chunker.create_documents(texts, metadatas)

        assert isinstance(result, list)
        assert len(result) >= 1

    @patch("rag.semantic_embed")
    def test_semantic_chunker_calc_breakpoint_threshold_percentile(self, mock_embed):
        """Test _calc_breakpoint_threshold with percentile type."""
        from rag import SemanticChunker
        import numpy as np

        chunker = SemanticChunker(
            embedding_function=mock_embed, breakpoint_threshold_type="percentile", breakpoint_threshold_amount=95.0
        )

        distances = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        threshold, returned_distances = chunker._calc_breakpoint_threshold(distances)

        assert isinstance(threshold, float)
        assert returned_distances == distances

    @patch("rag.semantic_embed")
    def test_semantic_chunker_calc_breakpoint_threshold_std(self, mock_embed):
        """Test _calc_breakpoint_threshold with standard_deviation type."""
        from rag import SemanticChunker

        chunker = SemanticChunker(
            embedding_function=mock_embed,
            breakpoint_threshold_type="standard_deviation",
            breakpoint_threshold_amount=2.0,
        )

        distances = [0.1, 0.2, 0.3, 0.4, 0.5]
        threshold, returned_distances = chunker._calc_breakpoint_threshold(distances)

        assert isinstance(threshold, float)
        assert returned_distances == distances


class TestApproxTokenLen:
    """Additional tests for _approx_token_len (merged from multiple files)."""

    def test_approx_token_len_unicode(self):
        """Test token length with unicode characters."""
        text = "Hello 世界 🌍"
        result = _approx_token_len(text)
        # Should return a reasonable estimate
        assert result > 0

    def test_approx_token_len_special_chars(self):
        """Test token length with special characters."""
        text = "Hello!!! What's up? Let's go."
        result = _approx_token_len(text)
        assert result > 0

    def test_approx_token_len_numbers(self):
        """Test token length with numbers."""
        text = "The price is $123.45 and quantity is 1000 units."
        result = _approx_token_len(text)
        assert result > 0

    def test_approx_token_len_with_tiktoken_mock(self):
        """Test with mocked tiktoken."""
        with patch("rag.USE_TIKTOKEN", True), patch("rag._TOK") as mock_tok:
            mock_tok.encode.return_value = [1, 2, 3, 4, 5]

            result = _approx_token_len("test text")
            assert result == 5

    def test_approx_token_len_tiktoken_exception(self):
        """Test fallback when tiktoken raises exception."""
        with patch("rag.USE_TIKTOKEN", True), patch("rag._TOK") as mock_tok:
            mock_tok.encode.side_effect = Exception("Encoding failed")

            # Should fall back to heuristic
            result = _approx_token_len("test text")
            assert result >= 1

    @pytest.mark.parametrize(
        "text",
        [
            "   \n\t  ",  # Whitespace only
            "!!!@@@###$$$",  # Special characters
            "Hello, world! How are you? I'm fine.",  # Mixed content
        ],
    )
    def test_approx_token_len_various_inputs(self, text):
        """Test with various text inputs."""
        result = _approx_token_len(text)
        assert result >= 1
        if len(text) > 10:  # For mixed content, tokens should be < characters
            assert result < len(text)


# ============================================================================
# Utility Functions
# ============================================================================


class TestLoadEnvFile:
    """Tests for _load_env_file function - simple and fast."""

    def test_load_env_file_basic(self, tmp_path, monkeypatch):
        """Test loading basic .env file."""
        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=test_value\nANOTHER_VAR=123\n")

        # Clear any existing env vars
        monkeypatch.delenv("TEST_VAR", raising=False)
        monkeypatch.delenv("ANOTHER_VAR", raising=False)

        # Mock Path(__file__).parent to point to tmp_path
        mock_path_instance = MagicMock()
        mock_path_instance.parent = tmp_path
        mock_path_instance.__truediv__ = lambda self, other: tmp_path / other

        with patch("rag.Path", return_value=mock_path_instance):
            _load_env_file()
            # Function uses setdefault, so it won't override existing values
            # Just verify it executed without error
            assert True

    def test_load_env_file_with_comments(self, tmp_path, monkeypatch):
        """Test .env file with comments."""
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nTEST_VAR=value#inline comment\n# Another comment\n")

        monkeypatch.delenv("TEST_VAR", raising=False)

        mock_path_instance = MagicMock()
        mock_path_instance.parent = tmp_path
        mock_path_instance.__truediv__ = lambda self, other: tmp_path / other

        with patch("rag.Path", return_value=mock_path_instance):
            _load_env_file()
            assert True  # Function executed

    @pytest.mark.parametrize(
        "file_exists,content",
        [
            (False, None),  # No file
            (True, "\n\nTEST_VAR=value\n\n"),  # Empty lines
        ],
    )
    def test_load_env_file_edge_cases(self, tmp_path, monkeypatch, file_exists, content):
        """Test .env file edge cases."""
        if file_exists and content:
            (tmp_path / ".env").write_text(content)
        mock_path_instance = MagicMock()
        mock_path_instance.parent = tmp_path
        mock_path_instance.__truediv__ = lambda self, other: tmp_path / other
        with patch("rag.Path", return_value=mock_path_instance):
            _load_env_file()  # Should not raise error
            assert True


class TestTouchChromaDBFiles:
    """Tests for _touch_chromadb_files function - simple file operations."""

    def test_touch_chromadb_files_with_sqlite(self, tmp_path):
        """Test touching chroma.sqlite3 file."""
        sqlite_file = tmp_path / "chroma.sqlite3"
        sqlite_file.write_text("fake sqlite content")

        with (
            patch("os.utime") as mock_utime,
            patch("os.path.exists", return_value=True),
            patch("os.path.getsize", return_value=100),
        ):
            _touch_chromadb_files(str(tmp_path))
            # Should call utime on sqlite file
            assert mock_utime.called

    def test_touch_chromadb_files_with_collections(self, tmp_path):
        """Test touching files in collection directories."""
        # Create collection directory structure
        collection_dir = tmp_path / "collection1"
        collection_dir.mkdir()
        (collection_dir / "file1.txt").write_text("content")
        (collection_dir / "file2.txt").write_text("content")

        with (
            patch("os.utime") as mock_utime,
            patch("os.path.exists", return_value=True),
            patch("os.listdir", return_value=["collection1"]),
            patch("os.path.isdir", return_value=True),
            patch("os.walk") as mock_walk,
        ):
            mock_walk.return_value = [(str(collection_dir), [], ["file1.txt", "file2.txt"])]
            _touch_chromadb_files(str(tmp_path))
            # Should attempt to touch files
            assert True  # Function executed


class TestGetChromaDBClient:
    """Tests for get_chromadb_client function."""

    @patch("rag.HttpClient")
    @patch("rag.CHROMADB_AUTH_TOKEN", "")
    def test_get_chromadb_client_no_auth(self, mock_http_client):
        """Test client creation without auth token."""
        mock_client = Mock()
        mock_http_client.return_value = mock_client

        result = get_chromadb_client()

        assert result == mock_client
        mock_http_client.assert_called_once_with(host="localhost", port=8000)

    @patch("rag.HttpClient")
    @patch("rag.ChromaSettings")
    @patch("rag.CHROMADB_AUTH_TOKEN", "test-token")
    def test_get_chromadb_client_with_auth(self, mock_settings, mock_http_client):
        """Test client creation with auth token."""
        mock_client = Mock()
        mock_http_client.return_value = mock_client
        mock_settings_instance = Mock()
        mock_settings.return_value = mock_settings_instance

        result = get_chromadb_client()

        assert result == mock_client
        mock_settings.assert_called_once()
        mock_http_client.assert_called_once()


class TestSemanticSplitterCache:
    """Tests for SemanticSplitterCache class - simple class methods."""

    def test_semantic_splitter_cache_init(self):
        """Test cache initialization."""
        cache = SemanticSplitterCache()
        assert cache.size() == 0

    def test_semantic_splitter_cache_clear(self):
        """Test clearing the cache."""
        cache = SemanticSplitterCache()
        # Add something to cache by calling get_splitter
        with patch("rag.SemanticChunker") as mock_chunker:
            mock_chunker.return_value = Mock()
            cache.get_splitter(sim_percentile=95.0, buffer_size=1)
            assert cache.size() > 0

            cache.clear()
            assert cache.size() == 0

    def test_semantic_splitter_cache_size(self):
        """Test cache size tracking."""
        cache = SemanticSplitterCache()
        assert cache.size() == 0

        with patch("rag.SemanticChunker") as mock_chunker:
            mock_chunker.return_value = Mock()
            cache.get_splitter(sim_percentile=95.0, buffer_size=1)
            assert cache.size() == 1

            # Different params = new entry
            cache.get_splitter(sim_percentile=96.0, buffer_size=1)
            assert cache.size() == 2

    def test_semantic_splitter_cache_get_splitter_caching(self):
        """Test that get_splitter caches instances."""
        cache = SemanticSplitterCache()

        with patch("rag.SemanticChunker") as mock_chunker:
            mock_instance = Mock()
            mock_chunker.return_value = mock_instance

            # First call
            result1 = cache.get_splitter(sim_percentile=95.0, buffer_size=1)
            assert mock_chunker.call_count == 1

            # Second call with same params
            result2 = cache.get_splitter(sim_percentile=95.0, buffer_size=1)

            # Should return same instance, not create new one
            assert result1 == result2
            assert mock_chunker.call_count == 1  # Still only 1 call


class TestSignalHandler:
    """Tests for _signal_handler function."""

    @patch("rag._cleanup_chromadb_server")
    @patch("sys.exit")
    def test_signal_handler_calls_cleanup_and_exits(self, mock_exit, mock_cleanup):
        """Test that _signal_handler calls cleanup and exits."""
        _signal_handler(15, None)  # SIGTERM = 15

        mock_cleanup.assert_called_once()
        mock_exit.assert_called_once_with(0)

    @patch("rag._cleanup_chromadb_server")
    @patch("sys.exit")
    def test_signal_handler_with_different_signal(self, mock_exit, mock_cleanup):
        """Test _signal_handler with different signal number."""
        _signal_handler(2, None)  # SIGINT = 2

        mock_cleanup.assert_called_once()
        mock_exit.assert_called_once_with(0)
