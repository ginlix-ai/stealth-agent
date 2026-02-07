import React, { useState, useRef, useEffect } from 'react';
import './TradingCenter.css';
import TopBar from './components/TopBar';
import StockHeader from './components/StockHeader';
import TradingChart from './components/TradingChart';
import TradingChatInput from './components/TradingChatInput';
import { fetchRealTimePrice, fetchStockInfo } from './utils/api';

function TradingCenter() {
  const [selectedStock, setSelectedStock] = useState('MSFT');
  const [selectedStockDisplay, setSelectedStockDisplay] = useState(null);
  const [stockInfo, setStockInfo] = useState(null);
  const [realTimePrice, setRealTimePrice] = useState(null);
  const [chartMeta, setChartMeta] = useState(null);
  const chartRef = useRef();

  const handleStockSearch = (symbol, searchResult) => {
    setSelectedStock(symbol);
    setSelectedStockDisplay(
      searchResult
        ? {
            name: searchResult.name || searchResult.symbol,
            exchange: searchResult.exchangeShortName || searchResult.stockExchange || '',
          }
        : null
    );
    setChartMeta(null);
  };

  // Fetch stock info and real-time price when selected stock changes
  useEffect(() => {
    if (!selectedStock) return;

    const loadStockData = async () => {
      try {
        // Fetch stock info and real-time price in parallel
        const [info, price] = await Promise.all([
          fetchStockInfo(selectedStock),
          fetchRealTimePrice(selectedStock).catch(() => null), // Don't fail if price fetch fails
        ]);
        
        setStockInfo(info);
        if (price) {
          setRealTimePrice(price);
        }
      } catch (error) {
        console.error('Error loading stock data:', error);
        // Set basic info on error
        setStockInfo({
          Symbol: selectedStock,
          Name: `${selectedStock} Corp`,
          Exchange: 'NASDAQ',
        });
      }
    };

    loadStockData();

    // Set up interval to refresh real-time price every minute
    const priceInterval = setInterval(async () => {
      try {
        const price = await fetchRealTimePrice(selectedStock);
        setRealTimePrice(price);
      } catch (error) {
        console.error('Error refreshing real-time price:', error);
      }
    }, 60000); // Refresh every minute

    return () => {
      clearInterval(priceInterval);
    };
  }, [selectedStock]);

  const handleCaptureChart = async () => {
    if (!chartRef.current) return;
    try {
      const blob = await chartRef.current.captureChart();
      if (blob) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${selectedStock}_chart_${new Date().getTime()}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('截图失败:', error);
    }
  };

  return (
    <div className="trading-center-container">
      <TopBar onStockSearch={handleStockSearch} />
      <div className="trading-content-wrapper">
        <div className="trading-left-panel">
          <StockHeader
            symbol={selectedStock}
            stockInfo={stockInfo}
            realTimePrice={realTimePrice}
            chartMeta={chartMeta}
            displayOverride={selectedStockDisplay}
          />
          <TradingChart
            ref={chartRef}
            symbol={selectedStock}
            onCapture={handleCaptureChart}
            onStockMeta={setChartMeta}
          />
        </div>
        <div className="trading-right-panel">
          <div className="trading-right-panel-inner">
            <TradingChatInput />
            <div className="trading-chat-empty">
              <p className="trading-chat-empty-title">Stealth Agent</p>
              <p className="trading-chat-empty-hint">Ask anything above to start a conversation. Your message will open in the Chat page.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TradingCenter;
