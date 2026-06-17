# NQ Paper Trading — Strategy Reference

## Account
- Starting Balance: $50,000 per strategy (tracked separately)
- Weekly Target: $3,000 total
- Instrument: NQ E-mini Nasdaq-100 Futures ($20/point)
- Rule: Do NOT overtrade to chase the weekly target

## Universal Risk Rules (Strat 1, Strat 2, Claude Day Trade)
- Risk:Reward = 1:2 minimum
- Move SL to Break Even when 1:1 is reached
- SL = most recent swing H or L at rejection point

---

## Strategy 1 — HTF Flow + Session Levels + Confluence (User S1)

### Bias
- Follow current HTF (Daily/4H) trend via BOS (Break of Structure)

### Draw on Liquidity (DOL) — in priority order
1. Session highs/lows: Asia H/L, London H/L, NY H/L
2. True Day Open (TDO) — midnight ET price
3. Unfilled FVGs above the 5m chart, or on the 5m chart

### Entry Conditions (ALL must align)
- Price is inside a FVG from any timeframe above 5m
- Price is rejecting off VWAP (main), VWAP +1, or VWAP -1 SD band
- Take Fib from most recent 15m swing high → low (or low → high)
- Price rejecting off .500, .618, .705, or .786 fib level
- Trigger: Rejection candle, IFVG (Inverse FVG), or Inverse Order Block

### Stop Loss
- Below/above the most recent swing H/L at rejection

---

## Strategy 2 — FVG + VWAP Absorption (User S2)

### Bias + DOL
- Same as Strategy 1

### Entry Conditions (ALL must align)
- Price is inside a FVG (any TF above 5m, or the 5m itself)
- A candle closes into VWAP
- Absorption of buyers (if bearish bias) or sellers (if bullish bias) is present
- Trigger: Rejection candle, IFVG, or OB inversion

### Stop Loss
- Most recent high of rejection candle (or statistically optimized placement)

---

## Claude Day Trading Strategy — Structure + VWAP Reclaim

### Bias
- 15m market structure: bullish (HH/HL) or bearish (LH/LL)
- Only trade in direction of 15m structure

### Draw on Liquidity
- Session H/L (Asia, London, NY)
- Previous day H/L
- Unfilled 5m/15m FVGs

### Entry Conditions
- 15m structure confirms direction
- Price pulls back into VWAP or a 15m order block
- 5m rejection candle forms at the level
- VWAP must be reclaimed (price closes back above/below VWAP on 5m)

### Stop Loss
- Below/above the 5m rejection candle wick

### Rules
- Max 3 trades per session
- 1:2 RR target, BE at 1:1
- No trades in first 5 min of NY open (9:30–9:35 ET)

---

## Claude Swing Strategy — Weekly Level Fades

### Bias
- Daily chart structure (BOS on Daily)
- Align with weekly trend direction

### Draw on Liquidity
- Prior week highs/lows
- Monthly open price
- Daily unfilled FVGs
- Quarterly highs/lows

### Entry Conditions
- Price reaches a prior week H/L or monthly level
- Daily candle shows rejection (wick, engulfing, or pin bar)
- 4H confirms with a BOS in favor of the trade direction

### Stop Loss
- Structural: above/below the rejection level + buffer
- Risk: 1% of current account balance per trade

### Targets
- Next key daily/weekly level in trade direction
- Hold up to 5 days; reassess if structure breaks

### Notes
- No fixed RR rule — managed by structure
- Can hold through overnight sessions
