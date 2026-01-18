"""Tests for yfinance MCP server tools.

This module tests all yfinance MCP server tools using mocked yfinance responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime

import sys
from pathlib import Path
# Add repo root to path to enable importing mcp_servers
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import all tools from the MCP server
from mcp_servers.yfinance_mcp_server import (
    # Original tools
    get_stock_history,
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
    get_options_chain,
    get_company_info,
    get_analyst_recommendations,
    get_institutional_holders,
    get_multiple_stocks_history,
    compare_financials,
    # New single-ticker tools
    get_dividends_and_splits,
    get_earnings_data,
    get_earnings_dates,
    get_insider_transactions,
    get_mutualfund_holders,
    get_sustainability_data,
    get_news,
    get_insider_roster,
    # New bulk tools
    get_multiple_stocks_dividends,
    get_multiple_stocks_earnings,
    compare_valuations,
)


# ============================================================================
# Fixtures for mock data
# ============================================================================

@pytest.fixture
def mock_history_df():
    """Create mock historical price DataFrame."""
    dates = pd.date_range('2024-01-01', periods=5, freq='D')
    return pd.DataFrame({
        'Open': [150.0, 151.0, 152.0, 151.5, 153.0],
        'High': [152.0, 153.0, 154.0, 153.5, 155.0],
        'Low': [149.0, 150.0, 151.0, 150.5, 152.0],
        'Close': [151.0, 152.0, 153.0, 152.5, 154.0],
        'Volume': [1000000, 1100000, 1200000, 1050000, 1300000],
        'Dividends': [0.0, 0.0, 0.24, 0.0, 0.0],
        'Stock Splits': [0.0, 0.0, 0.0, 0.0, 0.0],
    }, index=dates)


@pytest.fixture
def mock_dividends_series():
    """Create mock dividends Series."""
    dates = pd.date_range('2023-01-15', periods=4, freq='QE')
    return pd.Series([0.24, 0.24, 0.25, 0.25], index=dates)


@pytest.fixture
def mock_splits_series():
    """Create mock stock splits Series."""
    dates = pd.DatetimeIndex(['2020-08-31', '2014-06-09'])
    return pd.Series([4.0, 7.0], index=dates)


@pytest.fixture
def mock_earnings_df():
    """Create mock earnings DataFrame."""
    return pd.DataFrame({
        'Revenue': [100000000, 105000000, 110000000, 115000000],
        'Earnings': [20000000, 21000000, 22000000, 23000000],
    }, index=pd.PeriodIndex(['2024Q1', '2024Q2', '2024Q3', '2024Q4'], freq='Q'))


@pytest.fixture
def mock_earnings_dates_df():
    """Create mock earnings dates DataFrame."""
    dates = pd.DatetimeIndex(['2024-01-25', '2024-04-25', '2024-07-25', '2024-10-25'])
    return pd.DataFrame({
        'EPS Estimate': [1.50, 1.55, 1.60, 1.65],
        'Reported EPS': [1.52, 1.58, 1.62, None],
        'Surprise(%)': [1.33, 1.94, 1.25, None],
    }, index=dates)


@pytest.fixture
def mock_insider_transactions_df():
    """Create mock insider transactions DataFrame."""
    return pd.DataFrame({
        'Insider': ['John Doe', 'Jane Smith', 'Bob Wilson'],
        'Relation': ['CEO', 'CFO', 'Director'],
        'Date': pd.to_datetime(['2024-01-15', '2024-02-20', '2024-03-10']),
        'Transaction': ['Sale', 'Purchase', 'Purchase'],
        'Shares': [10000, 5000, 2000],
        'Value': [1500000, 750000, 300000],
    })


@pytest.fixture
def mock_holders_df():
    """Create mock institutional/mutual fund holders DataFrame."""
    return pd.DataFrame({
        'Holder': ['Vanguard Group', 'BlackRock', 'State Street'],
        'Shares': [1000000, 800000, 600000],
        'Date Reported': pd.to_datetime(['2024-03-31', '2024-03-31', '2024-03-31']),
        '% Out': [7.5, 6.0, 4.5],
        'Value': [150000000, 120000000, 90000000],
    })


@pytest.fixture
def mock_sustainability_df():
    """Create mock sustainability DataFrame."""
    data = {
        'Value': [25, 30, 20, 75]
    }
    return pd.DataFrame(data, index=['environmentScore', 'socialScore', 'governanceScore', 'totalEsg'])


@pytest.fixture
def mock_news_list():
    """Create mock news list."""
    return [
        {
            'title': 'AAPL Announces New Product',
            'publisher': 'Reuters',
            'link': 'https://example.com/news1',
            'providerPublishTime': 1704067200,  # 2024-01-01 00:00:00
            'type': 'STORY',
        },
        {
            'title': 'Quarterly Earnings Beat Expectations',
            'publisher': 'Bloomberg',
            'link': 'https://example.com/news2',
            'providerPublishTime': 1704153600,  # 2024-01-02 00:00:00
            'type': 'STORY',
        },
    ]


@pytest.fixture
def mock_insider_roster_df():
    """Create mock insider roster DataFrame."""
    return pd.DataFrame({
        'Name': ['Tim Cook', 'Luca Maestri', 'Jeff Williams'],
        'Position': ['CEO', 'CFO', 'COO'],
        'Most Recent Transaction': ['Sale', 'Sale', 'Sale'],
        'Shares Owned': [3000000, 500000, 400000],
    })


@pytest.fixture
def mock_company_info():
    """Create mock company info dict."""
    return {
        'symbol': 'AAPL',
        'shortName': 'Apple Inc.',
        'sector': 'Technology',
        'industry': 'Consumer Electronics',
        'marketCap': 3000000000000,
        'trailingPE': 28.5,
        'forwardPE': 25.0,
        'priceToBook': 45.0,
        'dividendYield': 0.005,
        'beta': 1.2,
        'fiftyTwoWeekHigh': 200.0,
        'fiftyTwoWeekLow': 150.0,
        'currentPrice': 185.0,
    }


# ============================================================================
# Tests for Original Tools
# ============================================================================

class TestGetStockHistory:
    """Tests for get_stock_history tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_history_df):
        """Test successful stock history retrieval."""
        mock_ticker = Mock()
        mock_ticker.history.return_value = mock_history_df
        mock_ticker_class.return_value = mock_ticker

        result = get_stock_history(ticker="AAPL", period="1mo", interval="1d")

        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert result["period"] == "1mo"
        assert result["interval"] == "1d"
        assert result["count"] == 5
        assert len(result["history"]) == 5
        assert result["history"][0]["date"] == "2024-01-01"
        assert result["history"][0]["open"] == 150.0
        assert result["history"][0]["close"] == 151.0

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_empty_data(self, mock_ticker_class):
        """Test when no data is found."""
        mock_ticker = Mock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        result = get_stock_history(ticker="INVALID")

        assert "error" in result
        assert "No data found" in result["error"]

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_exception(self, mock_ticker_class):
        """Test error handling."""
        mock_ticker_class.side_effect = Exception("API Error")

        result = get_stock_history(ticker="AAPL")

        assert "error" in result
        assert "Failed to fetch" in result["error"]


# ============================================================================
# Tests for New Single-Ticker Tools
# ============================================================================

class TestGetDividendsAndSplits:
    """Tests for get_dividends_and_splits tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_dividends_series, mock_splits_series):
        """Test successful dividends and splits retrieval."""
        mock_ticker = Mock()
        mock_ticker.dividends = mock_dividends_series
        mock_ticker.splits = mock_splits_series
        mock_ticker_class.return_value = mock_ticker

        result = get_dividends_and_splits(ticker="AAPL")

        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert result["dividend_count"] == 4
        assert result["split_count"] == 2
        assert len(result["dividends"]) == 4
        assert len(result["splits"]) == 2
        assert result["dividends"][0]["amount"] == 0.24
        assert result["splits"][0]["ratio"] == 4.0

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_no_dividends_or_splits(self, mock_ticker_class):
        """Test when stock has no dividends or splits."""
        mock_ticker = Mock()
        mock_ticker.dividends = pd.Series(dtype=float)
        mock_ticker.splits = pd.Series(dtype=float)
        mock_ticker_class.return_value = mock_ticker

        result = get_dividends_and_splits(ticker="GROWTH")

        assert "error" not in result
        assert result["dividend_count"] == 0
        assert result["split_count"] == 0

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_exception(self, mock_ticker_class):
        """Test error handling."""
        mock_ticker_class.side_effect = Exception("API Error")

        result = get_dividends_and_splits(ticker="AAPL")

        assert "error" in result


class TestGetEarningsData:
    """Tests for get_earnings_data tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_quarterly_success(self, mock_ticker_class, mock_earnings_df):
        """Test successful quarterly earnings retrieval."""
        mock_ticker = Mock()
        mock_ticker.quarterly_earnings = mock_earnings_df
        mock_ticker_class.return_value = mock_ticker

        result = get_earnings_data(ticker="AAPL", quarterly=True)

        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert result["quarterly"] is True
        assert result["count"] == 4
        assert len(result["earnings"]) == 4

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_annual_success(self, mock_ticker_class, mock_earnings_df):
        """Test successful annual earnings retrieval."""
        mock_ticker = Mock()
        mock_ticker.earnings = mock_earnings_df
        mock_ticker_class.return_value = mock_ticker

        result = get_earnings_data(ticker="AAPL", quarterly=False)

        assert "error" not in result
        assert result["quarterly"] is False

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_no_data(self, mock_ticker_class):
        """Test when no earnings data available."""
        mock_ticker = Mock()
        mock_ticker.quarterly_earnings = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        result = get_earnings_data(ticker="AAPL")

        assert "error" in result


class TestGetEarningsDates:
    """Tests for get_earnings_dates tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_earnings_dates_df):
        """Test successful earnings dates retrieval."""
        mock_ticker = Mock()
        mock_ticker.earnings_dates = mock_earnings_dates_df
        mock_ticker_class.return_value = mock_ticker

        result = get_earnings_dates(ticker="AAPL")

        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert result["count"] == 4
        assert len(result["earnings_dates"]) == 4

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_no_data(self, mock_ticker_class):
        """Test when no earnings dates available."""
        mock_ticker = Mock()
        mock_ticker.earnings_dates = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        result = get_earnings_dates(ticker="AAPL")

        assert "error" in result


class TestGetInsiderTransactions:
    """Tests for get_insider_transactions tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_insider_transactions_df):
        """Test successful insider transactions retrieval."""
        mock_ticker = Mock()
        mock_ticker.insider_transactions = mock_insider_transactions_df
        mock_ticker_class.return_value = mock_ticker

        result = get_insider_transactions(ticker="AAPL")

        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert result["count"] == 3
        assert len(result["transactions"]) == 3

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_no_data(self, mock_ticker_class):
        """Test when no insider transactions available."""
        mock_ticker = Mock()
        mock_ticker.insider_transactions = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        result = get_insider_transactions(ticker="AAPL")

        assert "error" in result


class TestGetMutualfundHolders:
    """Tests for get_mutualfund_holders tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_holders_df):
        """Test successful mutual fund holders retrieval."""
        mock_ticker = Mock()
        mock_ticker.mutualfund_holders = mock_holders_df
        mock_ticker_class.return_value = mock_ticker

        result = get_mutualfund_holders(ticker="AAPL")

        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert result["count"] == 3
        assert len(result["holders"]) == 3

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_no_data(self, mock_ticker_class):
        """Test when no mutual fund holder data available."""
        mock_ticker = Mock()
        mock_ticker.mutualfund_holders = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        result = get_mutualfund_holders(ticker="AAPL")

        assert "error" in result


class TestGetSustainabilityData:
    """Tests for get_sustainability_data tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_sustainability_df):
        """Test successful sustainability data retrieval."""
        mock_ticker = Mock()
        mock_ticker.sustainability = mock_sustainability_df
        mock_ticker_class.return_value = mock_ticker

        result = get_sustainability_data(ticker="AAPL")

        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert "scores" in result
        assert "environmentscore" in result["scores"]

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_no_data(self, mock_ticker_class):
        """Test when no sustainability data available."""
        mock_ticker = Mock()
        mock_ticker.sustainability = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        result = get_sustainability_data(ticker="AAPL")

        assert "error" in result


class TestGetNews:
    """Tests for get_news tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_news_list):
        """Test successful news retrieval."""
        mock_ticker = Mock()
        mock_ticker.news = mock_news_list
        mock_ticker_class.return_value = mock_ticker

        result = get_news(ticker="AAPL")

        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert result["count"] == 2
        assert len(result["news"]) == 2
        assert result["news"][0]["title"] == "AAPL Announces New Product"
        assert result["news"][0]["publisher"] == "Reuters"

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_no_news(self, mock_ticker_class):
        """Test when no news available."""
        mock_ticker = Mock()
        mock_ticker.news = []
        mock_ticker_class.return_value = mock_ticker

        result = get_news(ticker="AAPL")

        assert "error" in result


class TestGetInsiderRoster:
    """Tests for get_insider_roster tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_insider_roster_df):
        """Test successful insider roster retrieval."""
        mock_ticker = Mock()
        mock_ticker.insider_roster_holders = mock_insider_roster_df
        mock_ticker_class.return_value = mock_ticker

        result = get_insider_roster(ticker="AAPL")

        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert result["count"] == 3
        assert len(result["insiders"]) == 3

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_no_data(self, mock_ticker_class):
        """Test when no insider roster available."""
        mock_ticker = Mock()
        mock_ticker.insider_roster_holders = pd.DataFrame()
        mock_ticker_class.return_value = mock_ticker

        result = get_insider_roster(ticker="AAPL")

        assert "error" in result


# ============================================================================
# Tests for New Bulk Tools
# ============================================================================

class TestGetMultipleStocksDividends:
    """Tests for get_multiple_stocks_dividends tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_dividends_series):
        """Test successful multiple stocks dividends retrieval."""
        mock_ticker = Mock()
        mock_ticker.dividends = mock_dividends_series
        mock_ticker_class.return_value = mock_ticker

        result = get_multiple_stocks_dividends(tickers=["AAPL", "MSFT"])

        assert "error" not in result
        assert "AAPL" in result["data"]
        assert "MSFT" in result["data"]
        assert result["successful_tickers"] == ["AAPL", "MSFT"]
        assert result["total_dividends"] == 8  # 4 dividends × 2 stocks

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_partial_failure(self, mock_ticker_class, mock_dividends_series):
        """Test when some tickers fail."""
        def ticker_side_effect(symbol):
            mock = Mock()
            if symbol == "INVALID":
                raise Exception("Invalid ticker")
            mock.dividends = mock_dividends_series
            return mock

        mock_ticker_class.side_effect = ticker_side_effect

        result = get_multiple_stocks_dividends(tickers=["AAPL", "INVALID"])

        assert "AAPL" in result["data"]
        assert "INVALID" not in result["data"]
        assert "errors" in result
        assert len(result["errors"]) == 1


class TestGetMultipleStocksEarnings:
    """Tests for get_multiple_stocks_earnings tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_earnings_df):
        """Test successful multiple stocks earnings retrieval."""
        mock_ticker = Mock()
        mock_ticker.quarterly_earnings = mock_earnings_df
        mock_ticker_class.return_value = mock_ticker

        result = get_multiple_stocks_earnings(tickers=["AAPL", "MSFT"])

        assert "error" not in result
        assert result["quarterly"] is True
        assert "AAPL" in result["data"]
        assert "MSFT" in result["data"]
        assert result["successful_tickers"] == ["AAPL", "MSFT"]

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_annual(self, mock_ticker_class, mock_earnings_df):
        """Test annual earnings retrieval."""
        mock_ticker = Mock()
        mock_ticker.earnings = mock_earnings_df
        mock_ticker_class.return_value = mock_ticker

        result = get_multiple_stocks_earnings(tickers=["AAPL"], quarterly=False)

        assert result["quarterly"] is False


class TestCompareValuations:
    """Tests for compare_valuations tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_company_info):
        """Test successful valuations comparison."""
        mock_ticker = Mock()
        mock_ticker.info = mock_company_info
        mock_ticker_class.return_value = mock_ticker

        result = compare_valuations(tickers=["AAPL", "MSFT"])

        assert "error" not in result
        assert "AAPL" in result["data"]
        assert "MSFT" in result["data"]
        assert result["successful_tickers"] == ["AAPL", "MSFT"]

        # Check valuation metrics are present
        aapl_data = result["data"]["AAPL"]
        assert "trailing_p_e" in aapl_data
        assert "forward_p_e" in aapl_data
        assert "price_to_book" in aapl_data
        assert "dividend_yield" in aapl_data
        assert "market_cap" in aapl_data

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_partial_failure(self, mock_ticker_class, mock_company_info):
        """Test when some tickers fail."""
        def ticker_side_effect(symbol):
            mock = Mock()
            if symbol == "INVALID":
                mock.info = None
                return mock
            mock.info = mock_company_info
            return mock

        mock_ticker_class.side_effect = ticker_side_effect

        result = compare_valuations(tickers=["AAPL", "INVALID"])

        assert "AAPL" in result["data"]
        assert "INVALID" not in result["data"]
        assert "errors" in result


# ============================================================================
# Tests for Existing Tools (Coverage)
# ============================================================================

class TestGetCompanyInfo:
    """Tests for get_company_info tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_company_info):
        """Test successful company info retrieval."""
        mock_ticker = Mock()
        mock_ticker.info = mock_company_info
        mock_ticker_class.return_value = mock_ticker

        result = get_company_info(ticker="AAPL")

        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert "info" in result
        assert result["info"]["shortName"] == "Apple Inc."


class TestGetInstitutionalHolders:
    """Tests for get_institutional_holders tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_holders_df):
        """Test successful institutional holders retrieval."""
        mock_ticker = Mock()
        mock_ticker.institutional_holders = mock_holders_df
        mock_ticker_class.return_value = mock_ticker

        result = get_institutional_holders(ticker="AAPL")

        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert result["count"] == 3


class TestGetAnalystRecommendations:
    """Tests for get_analyst_recommendations tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class):
        """Test successful analyst recommendations retrieval."""
        mock_recs = pd.DataFrame({
            'Firm': ['Goldman Sachs', 'Morgan Stanley'],
            'To Grade': ['Buy', 'Overweight'],
            'From Grade': ['Hold', 'Equal-Weight'],
            'Action': ['up', 'up'],
        }, index=pd.DatetimeIndex(['2024-01-15', '2024-02-20']))

        mock_ticker = Mock()
        mock_ticker.recommendations = mock_recs
        mock_ticker_class.return_value = mock_ticker

        result = get_analyst_recommendations(ticker="AAPL")

        assert "error" not in result
        assert result["ticker"] == "AAPL"
        assert result["count"] == 2


class TestGetMultipleStocksHistory:
    """Tests for get_multiple_stocks_history tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_success(self, mock_ticker_class, mock_history_df):
        """Test successful multiple stocks history retrieval."""
        mock_ticker = Mock()
        mock_ticker.history.return_value = mock_history_df
        mock_ticker_class.return_value = mock_ticker

        result = get_multiple_stocks_history(tickers=["AAPL", "MSFT"])

        assert "error" not in result
        assert "AAPL" in result["data"]
        assert "MSFT" in result["data"]
        assert result["successful_tickers"] == ["AAPL", "MSFT"]
        assert result["total_data_points"] == 10  # 5 × 2


class TestCompareFinancials:
    """Tests for compare_financials tool."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_income_statement(self, mock_ticker_class):
        """Test comparing income statements."""
        mock_df = pd.DataFrame({
            '2024-03-31': [100000000, 70000000],
            '2024-06-30': [105000000, 73000000],
        }, index=['Total Revenue', 'Cost Of Revenue'])
        mock_df.columns = pd.to_datetime(mock_df.columns)

        mock_ticker = Mock()
        mock_ticker.quarterly_income_stmt = mock_df
        mock_ticker_class.return_value = mock_ticker

        result = compare_financials(tickers=["AAPL", "MSFT"], statement_type="income")

        assert "error" not in result
        assert result["statement_type"] == "income"
        assert "AAPL" in result["data"]
        assert "MSFT" in result["data"]


# ============================================================================
# Integration-style tests
# ============================================================================

class TestDataSerialization:
    """Tests for data serialization helpers."""

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_nan_handling(self, mock_ticker_class):
        """Test that NaN values are properly handled."""
        mock_df = pd.DataFrame({
            'Holder': ['Vanguard', 'BlackRock'],
            'Shares': [1000000, np.nan],  # NaN value
            'Value': [150000000, 120000000],
        })

        mock_ticker = Mock()
        mock_ticker.institutional_holders = mock_df
        mock_ticker_class.return_value = mock_ticker

        result = get_institutional_holders(ticker="AAPL")

        assert "error" not in result
        # NaN should be converted to None
        holders = result["holders"]
        assert holders[1]["Shares"] is None or holders[1].get("shares") is None

    @patch('mcp_servers.yfinance_mcp_server.yf.Ticker')
    def test_datetime_handling(self, mock_ticker_class):
        """Test that datetime values are properly serialized."""
        mock_df = pd.DataFrame({
            'Holder': ['Vanguard'],
            'Date Reported': [pd.Timestamp('2024-03-31')],
        })

        mock_ticker = Mock()
        mock_ticker.institutional_holders = mock_df
        mock_ticker_class.return_value = mock_ticker

        result = get_institutional_holders(ticker="AAPL")

        assert "error" not in result
        # Datetime should be converted to ISO format string
        holder = result["holders"][0]
        date_val = holder.get("Date Reported") or holder.get("date_reported")
        assert isinstance(date_val, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
