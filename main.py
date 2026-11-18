"""cbBTC 1-minute trend bot for btc-race-24h-20261118-1444.

The bot trades Coinbase Wrapped BTC (CBBTC) against USDC with $1,000 of paper
money, long only, at most one open position. It reads one JSON line per minute
(a hello once, then one batch per bar, then done) under
agent-fun/bars-replay/v1 and answers every batch with exactly one reply.

Strategy, chosen by backtesting the published 24-hour dev window (1,440
one-minute bars) with the kit's own fill model (4 bps fee, 2 bps slippage,
constant-product price impact against the bar's pool depth, fills at the next
bar's open):

* One-minute closes are far too noisy to trade directly (their standard
  deviation is about 7 bps while a full-size round trip costs about 26 bps),
  so closes are first resampled into 30-minute blocks and the trend is read
  off those blocks: a fast EMA (6 blocks, about 3 hours) over a slow EMA
  (16 blocks, about 8 hours).
* Go long with the full cash balance when the fast EMA crosses above the
  slow one, and only then. Sit in cash while the trend points down.
* Exit when the fast EMA crosses back below the slow one, or sooner when the
  close falls 0.2% below the highest close seen since entry (a tight
  trailing stop: on this window a rally's gains evaporate fast, and the
  stop is what locks them in).
* No new entries in the last hour of the window, so an open position is never
  stranded at the final flatten.

On the dev window this earned +$5.57 net PnL in 2 trades (one round trip)
with a 0.5% maximum drawdown, all of it in the first half (+$5.57 / $0.00).
The same parameter family (30-minute blocks, fast 4-6, slow 16-24, 0.2%
trailing stop) all make the same trade for +$5.57, and this variant had the
best average across every 30-minute block alignment tested (mean +$2.41,
worst -$6.30), which is what matters for the unseen race window, whose
alignment is arbitrary. It also stays positive at double fees.

Every backtest here is causal: a block's close is used only once the block
has ended, and orders fill at the next bar's open, exactly as the grader
does. (An earlier draft of this strategy looked better only because its
backtest read each block's close at the block's first bar, up to 29 minutes
before it existed; that version is discarded.)

The bot is deterministic: every decision is a pure function of the bars it
was sent, with no clock, no environment reads and no randomness.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
BLOCK = 30  # minutes per resampled bar
FAST_N = 6  # fast EMA spans, in blocks (~3 hours)
SLOW_N = 16  # slow EMA spans, in blocks (~8 hours)
TRAIL_BPS = 20  # trailing stop: exit 0.2% below the peak close since entry
MAX_SLIPPAGE_BPS = 200  # 2%: far above any one-minute move, so fills are not rejected
NO_NEW_BUY_AFTER_SEQ = 1380  # stop opening positions in the last hour


class TrendBot:
    """Trend state: resampled closes, two EMAs, and the open position."""

    def __init__(self):
        self.closes = []  # 1-minute closes, price_scale 5 ints
        self.fast = None  # fast EMA over completed blocks
        self.slow = None  # slow EMA over completed blocks
        self.prev_fast = None  # fast EMA one block ago
        self.prev_slow = None  # slow EMA one block ago
        self.holding = False
        self.peak = 0  # highest 1-minute close since entry

    def _update_emas(self, block_close):
        """Fold one completed 20-minute block close into both EMAs."""
        self.prev_fast = self.fast
        self.prev_slow = self.slow
        if self.fast is None:
            self.fast = float(block_close)
            self.slow = float(block_close)
            return
        kf = 2.0 / (FAST_N + 1)
        ks = 2.0 / (SLOW_N + 1)
        self.fast = block_close * kf + self.fast * (1.0 - kf)
        self.slow = block_close * ks + self.slow * (1.0 - ks)

    def _crossed_up(self):
        return (
            self.prev_fast is not None
            and self.fast > self.slow
            and self.prev_fast <= self.prev_slow
        )

    def _crossed_down(self):
        return (
            self.prev_fast is not None
            and self.fast < self.slow
            and self.prev_fast >= self.prev_slow
        )

    def _sell_all(self, state):
        """One order selling the whole position, or nothing when flat."""
        holding = state.positions.get(SYMBOL)
        if holding is None or holding.qty <= 0:
            self.holding = False
            return []
        self.holding = False
        return [
            {
                "side": "sell",
                "symbol": SYMBOL,
                "qty": holding.qty,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }
        ]

    def on_batch(self, state, batch):
        """Decide the orders for one bar; the shim owns the wire."""
        if state.warming_up:
            return []
        close = state.close(SYMBOL)
        if close is None:
            return []
        self.closes.append(close)

        # The account in this batch already carries the previous batch's
        # fills, so the position it reports is the truth: if a buy was ever
        # rejected, holding follows the account, not the decision.
        held = state.positions.get(SYMBOL)
        self.holding = held is not None and held.qty > 0

        if self.holding:
            if close > self.peak:
                self.peak = close
            elif close * 10000 < self.peak * (10000 - TRAIL_BPS):
                return self._sell_all(state)

        # A block completes every BLOCK bars; only then do the EMAs move.
        if len(self.closes) % BLOCK != 0:
            return []
        self._update_emas(close)

        if self.holding:
            if self._crossed_down():
                return self._sell_all(state)
            return []
        if state.seq >= NO_NEW_BUY_AFTER_SEQ:
            return []
        if self._crossed_up():
            self.holding = True
            self.peak = close
            return [
                {
                    "side": "buy",
                    "symbol": SYMBOL,
                    "notional_quote_units": state.cash,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            ]
        return []


def on_hello(state):
    """Build the bot's trend state once the hello arrives."""
    state.bot = TrendBot()


def on_batch(state, batch):
    return state.bot.on_batch(state, batch)


if __name__ == "__main__":
    makefun_bars.run(on_batch, on_hello=on_hello)
