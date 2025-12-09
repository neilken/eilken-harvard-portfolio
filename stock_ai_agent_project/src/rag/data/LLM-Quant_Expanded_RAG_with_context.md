# LLM‑Quant Stock Screener – Expanded Feature Glossary With Finance Context

## symbol
**Definition / Formula:** Stock ticker symbol

**Meaning:** Identifies the stock (e.g., AAPL, MSFT)

**Interpretation / Signal:** Used to map all metrics and charts to the company.

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## pred_prob_next_month
**Definition / Formula:** Probability of outperforming SP500 next month

**Meaning:** Random Forest model prediction

**Interpretation / Signal:** Higher value = higher chance to beat SPX next month.

**Financial Context:** Model‑generated predictive metric used to estimate short‑term performance or directional bias.

---

## signal
**Definition / Formula:** Model-based trading signal

**Meaning:** Directional signal based on predicted probability thresholds

**Interpretation / Signal:** LONG-Outperform / SHORT-Underperform / NEUTRAL

**Financial Context:** Model‑generated predictive metric used to estimate short‑term performance or directional bias.

---

## Hybrid_Score
**Definition / Formula:** (Fundamental_Score + Technical_Score) / 2

**Meaning:** Overall blended strength score

**Interpretation / Signal:** Higher = stronger combined outlook

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## Fundamental_Score
**Definition / Formula:** Average percentile of fundamental indicators

**Meaning:** Long-term business quality & valuation

**Interpretation / Signal:** Higher = better long-term fundamentals

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## Technical_Score
**Definition / Formula:** Average percentile of technical indicators

**Meaning:** Short-term momentum & price trend strength

**Interpretation / Signal:** Higher = stronger near-term momentum

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## Hybrid_Rank
**Definition / Formula:** Rank of Hybrid_Score across universe

**Meaning:** Relative rank position

**Interpretation / Signal:** Rank 1 = strongest overall

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## Hybrid_CS_Pct
**Definition / Formula:** Cross-sectional percentile of Hybrid Score (0–1)

**Meaning:** Relative strength vs all stocks

**Interpretation / Signal:** >0.70 = top 30%, strong conviction zone

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## H_Score Recommendation
**Definition / Formula:** Categorical ML + Hybrid interpretation

**Meaning:** Human-readable signal combining fundamentals, technicals, and model

**Interpretation / Signal:** E.g., Short-Term Buy (Momentum), Long-Term Buy, Balanced, Avoid

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## date
**Definition / Formula:** Date of snapshot

**Meaning:** Data timestamp for prediction

**Interpretation / Signal:** Represents when metrics were generated

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## roe
**Definition / Formula:** Return on Equity = Net Income / Shareholder Equity

**Meaning:** Profitability relative to equity

**Interpretation / Signal:** High ROE >15% = efficient management

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## roic
**Definition / Formula:** NOPAT / (Debt + Equity – Cash)

**Meaning:** Return generated on invested capital

**Interpretation / Signal:** ROIC >10% = strong competitive advantage

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## peRatio
**Definition / Formula:** Price / EPS

**Meaning:** Valuation multiple

**Interpretation / Signal:** Low PE = undervalued; High PE = growth premium

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## freeCashFlowYield
**Definition / Formula:** Free Cash Flow / Market Cap

**Meaning:** Cash-generation efficiency

**Interpretation / Signal:** High yield = undervaluation & strong FCF

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## debtToEquity
**Definition / Formula:** Total Debt / Shareholder Equity

**Meaning:** Leverage and capital structure risk

**Interpretation / Signal:** High D/E >2 = risky; Low D/E = stable

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## currentRatio
**Definition / Formula:** Current Assets / Current Liabilities

**Meaning:** Liquidity indicator

**Interpretation / Signal:** >1 = healthy; <1 = liquidity stress

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## dividendYield
**Definition / Formula:** Dividend / Price

**Meaning:** Return provided via dividends

**Interpretation / Signal:** High yield = stable income; too high may signal distress

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## earningsYield
**Definition / Formula:** Earnings / Price

**Meaning:** Inverse PE valuation measure

**Interpretation / Signal:** High earnings yield = undervalued

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## payoutRatio
**Definition / Formula:** Dividends / Earnings

**Meaning:** Profit share returned to shareholders

**Interpretation / Signal:** Low payout = reinvestment potential; high = income stability

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## cashPerShare
**Definition / Formula:** Total Cash / Shares Outstanding

**Meaning:** Cash buffer & liquidity

**Interpretation / Signal:** High = strong cash reserves

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## revenuePerShare
**Definition / Formula:** Revenue / Shares

**Meaning:** Revenue efficiency per share

**Interpretation / Signal:** Growing value = strong top-line growth

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## return_1m
**Definition / Formula:** (Close_today / Close_21_days_ago) - 1

**Meaning:** 1-month price momentum

**Interpretation / Signal:** Positive = bullish; negative = bearish

**Financial Context:** Common technical indicator used by traders to evaluate momentum, price trends, or market sentiment.

---

## ema_12
**Definition / Formula:** 12-day EMA

**Meaning:** Short-term trend smoothing

**Interpretation / Signal:** Rising EMA = bullish momentum

**Financial Context:** Common technical indicator used by traders to evaluate momentum, price trends, or market sentiment.

---

## ema_26
**Definition / Formula:** 26-day EMA

**Meaning:** Longer-term trend smoothing

**Interpretation / Signal:** EMA12 > EMA26 = bullish crossover

**Financial Context:** Common technical indicator used by traders to evaluate momentum, price trends, or market sentiment.

---

## macd
**Definition / Formula:** EMA12 - EMA26

**Meaning:** Momentum indicator

**Interpretation / Signal:** Positive = bullish; negative = bearish

**Financial Context:** Common technical indicator used by traders to evaluate momentum, price trends, or market sentiment.

---

## macd_signal
**Definition / Formula:** 9-day EMA of MACD

**Meaning:** Signal line for crossovers

**Interpretation / Signal:** MACD > signal = buy; MACD < signal = sell

**Financial Context:** Common technical indicator used by traders to evaluate momentum, price trends, or market sentiment.

---

## macd_hist
**Definition / Formula:** MACD - MACD_signal

**Meaning:** Momentum strength histogram

**Interpretation / Signal:** Positive = bullish; negative = bearish

**Financial Context:** Common technical indicator used by traders to evaluate momentum, price trends, or market sentiment.

---

## RSI_14
**Definition / Formula:** 14-day Relative Strength Index

**Meaning:** Overbought/oversold momentum indicator

**Interpretation / Signal:** <30 oversold (buy); >70 overbought (sell)

**Financial Context:** Common technical indicator used by traders to evaluate momentum, price trends, or market sentiment.

---

## volatility_21d
**Definition / Formula:** 21-day return std dev

**Meaning:** Short-term price volatility

**Interpretation / Signal:** High volatility = unstable; low = steady

**Financial Context:** Common technical indicator used by traders to evaluate momentum, price trends, or market sentiment.

---

## n_periods
**Definition / Formula:** Months of backtest data

**Meaning:** Number of periods used for metrics

**Interpretation / Signal:** More history = more reliable

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## avg_fwd_1m_ret
**Definition / Formula:** Average 1-month forward return

**Meaning:** Expected monthly gain

**Interpretation / Signal:** Higher = stronger short-term return

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## vol_1m
**Definition / Formula:** 1-month volatility

**Meaning:** Return variability

**Interpretation / Signal:** High = risky; low = stable

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## sharpe_1m_annual
**Definition / Formula:** Annualized Sharpe Ratio

**Meaning:** Risk-adjusted performance

**Interpretation / Signal:** >1 good; >2 excellent; >3 elite

**Financial Context:** Measures fundamental financial health, profitability, or valuation used by investors to assess long‑term business quality.

---

## max_drawdown
**Definition / Formula:** Worst historical drop

**Meaning:** Downside risk

**Interpretation / Signal:** Closer to 0 = safer; deep negative = risky

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## hit_rate_pos
**Definition / Formula:** % positive months

**Meaning:** Consistency of gains

**Interpretation / Signal:** Higher = more reliable winner

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## hit_rate_vs_sp500
**Definition / Formula:** % months beating SP500

**Meaning:** Relative outperformance consistency

**Interpretation / Signal:** Higher = stronger alpha generation

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## cagr
**Definition / Formula:** Compound Annual Growth Rate

**Meaning:** Annualized long-term growth from backtest

**Interpretation / Signal:** High CAGR = strong long-term compounder

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## equity_chart_path
**Definition / Formula:** Chart path

**Meaning:** Path to equity curve image

**Interpretation / Signal:** Used for UI visualization

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## sector
**Definition / Formula:** Sector

**Meaning:** Stock sector classification

**Interpretation / Signal:** Used for sector filtering

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

## industry
**Definition / Formula:** Industry

**Meaning:** Stock industry classification

**Interpretation / Signal:** Used for industry-level analysis

**Financial Context:** General metric used in quant models or metadata supporting stock screening workflows.

---

