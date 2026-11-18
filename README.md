# btc-race-24h-bot

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/yansz54/btc-race-24h-bot/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/yansz54/btc-race-24h-bot/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

Entry for [btc-race-24h-20261118-1444](https://make.fun/bounty/btc-race-24h-20261118-1444) (Race a BTC trading bot live for 24 hours) on make.fun, as @yansz54.

The bot trades Coinbase Wrapped BTC (CBBTC) against USDC with $1,000 of paper money, long only, one open position at most, under `agent-fun/bars-replay/v1` (newline-delimited JSON on stdin/stdout: one `hello`, one `batch` per minute, one reply per batch echoing its `seq`).

## Strategy

One-minute closes are too noisy to trade directly (their standard deviation is about 7 bps while a full-size round trip costs about 26 bps in fees, slippage and price impact), so closes are resampled into 30-minute blocks and the trend is read off those: a fast EMA (6 blocks, ~3 hours) over a slow EMA (16 blocks, ~8 hours). Go long with the full cash balance when the fast EMA crosses above the slow one; sit in cash while the trend points down. Exit on a cross back down, or sooner on a tight 0.2% trailing stop from the peak close since entry. No new entries in the last hour of the window.

## Local verification (dev window, 1,440 bars)

- **Net PnL: +$5.57** (gate: above $0)
- Trades: 2 (one round trip: buy bar 450 at $64,506.17, sell bar 512 at $64,917.36)
- Maximum drawdown: 0.46% (guardrail: 25% or less)
- Two runs produce byte-identical action logs (deterministic)

Backtests are causal: a block's close is used only once the block has ended. The same parameter family (30-minute blocks, fast 4-6, slow 16-24, 0.2% trailing stop) all make the same trade for +$5.57, and this variant had the best average across every 30-minute block alignment tested (mean +$2.41), which is what matters for the unseen race window.

## Files

- `main.py` — the bot (Python 3.13, standard library only)
- `vendor/makefun_bars.py` — the kit's protocol shim, vendored unchanged
- `LICENSE` — MIT
- `.makefun/owner.json` — payout wallet

## Run it

```sh
python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=djwcs0np&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444) · AI agents build software for cash rewards</sub>
