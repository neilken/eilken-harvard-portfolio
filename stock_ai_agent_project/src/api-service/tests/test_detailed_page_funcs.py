"""
Unit tests for detailed page utility functions.
"""

import pytest
import pandas as pd

pytestmark = pytest.mark.unit
from api.utils.detailed_page_funcs import (
    get_company_profile,
    get_quant_data,
    get_stocks_data,
    user_pref_stock_selection,
)


class TestGetCompanyProfile:
    """Tests for get_company_profile function."""

    def test_existing_ticker_returns_profile(self, sample_company_profile):
        """Test getting company profile for existing ticker."""
        result = get_company_profile("AAPL", sample_company_profile)
        assert result["symbol"] == "AAPL"
        assert result["companyName"] == "Apple Inc."
        assert result["sector"] == "Technology"

    def test_lowercase_ticker_converted_to_uppercase(self, sample_company_profile):
        """Test that lowercase ticker is converted to uppercase."""
        result = get_company_profile("aapl", sample_company_profile)
        assert result["symbol"] == "AAPL"

    def test_mixed_case_ticker(self, sample_company_profile):
        """Test mixed case ticker handling."""
        result = get_company_profile("AaPl", sample_company_profile)
        assert result["symbol"] == "AAPL"

    def test_nonexistent_ticker_returns_zero(self, sample_company_profile):
        """Test getting company profile for non-existent ticker returns 0."""
        result = get_company_profile("INVALID", sample_company_profile)
        assert result == 0

    def test_empty_dataframe_returns_zero(self):
        """Test with empty dataframe returns 0."""
        empty_df = pd.DataFrame(columns=["symbol", "companyName"])
        result = get_company_profile("AAPL", empty_df)
        assert result == 0

    def test_all_fields_present(self, sample_company_profile):
        """Test that all expected fields are present in result."""
        result = get_company_profile("GOOGL", sample_company_profile)
        expected_fields = [
            "symbol",
            "companyName",
            "industry",
            "sector",
            "country",
            "exchange",
            "marketCap",
            "description",
        ]
        for field in expected_fields:
            assert field in result


class TestGetQuantData:
    """Tests for get_quant_data function."""

    def test_existing_ticker_returns_data(self, sample_quant_data):
        """Test getting quant data for existing ticker."""
        result = get_quant_data("AAPL", sample_quant_data)
        assert result["symbol"] == "AAPL"
        assert result["Hybrid_Score"] == 0.85
        assert result["sector"] == "Technology"

    def test_lowercase_ticker_converted(self, sample_quant_data):
        """Test that lowercase ticker is converted to uppercase."""
        result = get_quant_data("googl", sample_quant_data)
        assert result["symbol"] == "GOOGL"

    def test_nonexistent_ticker_returns_zero(self, sample_quant_data):
        """Test getting quant data for non-existent ticker returns 0."""
        result = get_quant_data("INVALID", sample_quant_data)
        assert result == 0

    def test_all_scores_present(self, sample_quant_data):
        """Test that all score types are present."""
        result = get_quant_data("MSFT", sample_quant_data)
        assert "Hybrid_Score" in result
        assert "Technical_Score" in result
        assert "Fundamental_Score" in result

    def test_recommendation_field_present(self, sample_quant_data):
        """Test that recommendation field is present."""
        result = get_quant_data("AAPL", sample_quant_data)
        assert "H_Score Recommendation" in result


class TestGetStocksData:
    """Tests for get_stocks_data function."""

    def test_existing_ticker_returns_data(self, sample_stocks_data):
        """Test getting stocks data for existing ticker."""
        result = get_stocks_data("AAPL", sample_stocks_data)
        assert "open" in result
        assert "close" in result
        assert "volume" in result
        assert len(result["open"]) == 30

    def test_lowercase_ticker_converted(self, sample_stocks_data):
        """Test that lowercase ticker is converted to uppercase."""
        result = get_stocks_data("googl", sample_stocks_data)
        assert len(result["close"]) == 30

    def test_nonexistent_ticker_returns_empty_lists(self, sample_stocks_data):
        """Test getting stocks data for non-existent ticker returns empty lists."""
        result = get_stocks_data("INVALID", sample_stocks_data)
        assert result["open"] == []
        assert result["close"] == []

    def test_ohlcv_fields_present(self, sample_stocks_data):
        """Test all OHLCV fields are present."""
        result = get_stocks_data("MSFT", sample_stocks_data)
        expected_fields = ["open", "high", "low", "close", "volume"]
        for field in expected_fields:
            assert field in result


class TestUserPrefStockSelection:
    """Tests for user_pref_stock_selection function."""

    def test_long_term_low_risk_selection(self, sample_quant_data, user_preferences_long_term):
        """Test stock selection for long-term, low-risk preferences."""
        result = user_pref_stock_selection(sample_quant_data, user_preferences_long_term)
        assert "symbol" in result
        symbols = result["symbol"]
        assert isinstance(symbols, list)

    def test_short_term_high_risk_selection(self, sample_quant_data, user_preferences_short_term):
        """Test stock selection for short-term, high-risk preferences."""
        result = user_pref_stock_selection(sample_quant_data, user_preferences_short_term)
        assert "symbol" in result

    def test_balanced_selection(self, sample_quant_data, user_preferences_balanced):
        """Test stock selection for balanced preferences."""
        result = user_pref_stock_selection(sample_quant_data, user_preferences_balanced)
        assert "symbol" in result

    def test_neither_long_nor_short_defaults_to_hybrid(self, sample_quant_data):
        """Test when neither long nor short term selected defaults to hybrid."""
        user_pref = {
            "long_term": False,
            "short_term": False,
            "high_risk": False,
            "low_risk": False,
        }
        result = user_pref_stock_selection(sample_quant_data, user_pref)
        assert "symbol" in result

    def test_both_long_and_short_term(self, sample_quant_data):
        """Test when both long and short term are selected."""
        user_pref = {
            "long_term": True,
            "short_term": True,
            "high_risk": False,
            "low_risk": True,
        }
        result = user_pref_stock_selection(sample_quant_data, user_pref)
        assert "symbol" in result

    def test_low_risk_filter_excludes_high_volatility(self, sample_quant_data):
        """Test that low risk filter excludes high volatility stocks."""
        user_pref = {
            "long_term": True,
            "short_term": False,
            "high_risk": False,
            "low_risk": True,
        }
        result = user_pref_stock_selection(sample_quant_data, user_pref)
        # TSLA has volatility 0.08 which should be excluded
        if result["symbol"]:
            assert "TSLA" not in result["symbol"]

    def test_returns_required_columns(self, sample_quant_data, user_preferences_long_term):
        """Test that all required columns are returned."""
        result = user_pref_stock_selection(sample_quant_data, user_preferences_long_term)
        required_columns = ["symbol", "Hybrid_Score", "volatility_21d"]
        for col in required_columns:
            assert col in result

    def test_results_sorted_by_score(self, sample_quant_data, user_preferences_balanced):
        """Test that results are sorted by score descending."""
        result = user_pref_stock_selection(sample_quant_data, user_preferences_balanced)
        if len(result["Hybrid_Score"]) > 1:
            scores = result["Hybrid_Score"]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1]
