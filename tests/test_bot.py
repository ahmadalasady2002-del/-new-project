import math
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from bot import config, data, indicators, main, strategy
from bot.broker import PaperBroker


def candles_from(closes, vols=None):
    out = []
    for i, c in enumerate(closes):
        prev = closes[i - 1] if i else c
        out.append({"time": i * 3600, "open": prev, "high": max(prev, c) * 1.002,
                    "low": min(prev, c) * 0.998, "close": c, "volume": (vols or [100] * len(closes))[i]})
    return out


def uptrend(n=260, start=100.0, step=0.001):
    return [start * (1 + step) ** i * (1 + 0.02 * math.sin(i / 3)) for i in range(n)]


class IndicatorTests(unittest.TestCase):
    def test_ema_constant(self):
        self.assertAlmostEqual(indicators.ema([5.0] * 30, 10)[-1], 5.0)

    def test_rsi_bounds(self):
        self.assertEqual(indicators.rsi(list(range(1, 40)), 14)[-1], 100.0)
        r = indicators.rsi(uptrend(), 14)[-1]
        self.assertTrue(0 <= r <= 100)

    def test_atr_positive(self):
        self.assertGreater(indicators.atr(candles_from(uptrend())), 0)


class StrategyTests(unittest.TestCase):
    def test_breakout_detected(self):
        closes = uptrend()
        closes[-1] = max(closes[-21:-1]) * 1.005
        vols = [100] * len(closes)
        vols[-1] = 500
        sig = strategy.evaluate("XUSDT", candles_from(closes, vols))
        self.assertIsNotNone(sig)
        self.assertIn("breakout", sig.reason)

    def test_dip_detected(self):
        closes = [100 * 1.004 ** i for i in range(250)]
        for _ in range(7):
            closes.append(closes[-1] * 0.985)
        closes.append(closes[-1] * 1.01)
        sig = strategy.evaluate("XUSDT", candles_from(closes))
        self.assertIsNotNone(sig)
        self.assertIn("dip", sig.reason)

    def test_downtrend_no_signal(self):
        closes = [100 * 0.998 ** i for i in range(260)]
        self.assertIsNone(strategy.evaluate("XUSDT", candles_from(closes)))

    def test_regime(self):
        up = candles_from(uptrend(120))
        down = candles_from([100 * 0.99 ** i for i in range(120)])
        self.assertEqual(strategy.market_regime(up, 50), "on")
        self.assertEqual(strategy.market_regime(up, 90), "caution")
        self.assertEqual(strategy.market_regime(down, 80), "off")


class UniverseTests(unittest.TestCase):
    def test_filters(self):
        tickers = [
            {"symbol": "BTCUSDT", "quoteVolume": "1e9", "lastPrice": "1"},
            {"symbol": "USDCUSDT", "quoteVolume": "1e9", "lastPrice": "1"},
            {"symbol": "ETHBTC", "quoteVolume": "1e9", "lastPrice": "1"},
            {"symbol": "PEPEUSDT", "quoteVolume": "6e6", "lastPrice": "1"},
            {"symbol": "TINYUSDT", "quoteVolume": "1e5", "lastPrice": "1"},
        ]
        self.assertEqual(data.build_universe(tickers, {"PEPE", "TINY"}), ["BTCUSDT", "PEPEUSDT"])


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [
            mock.patch.object(config, "STATE_FILE", Path(self.tmp.name) / "state.json"),
            mock.patch.object(config, "LOG_FILE", Path(self.tmp.name) / "bot.log"),
            mock.patch.object(config, "LIVE_TRADING", False),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def run_cycle(self, state, price, signal_closes):
        tickers = [{"symbol": "XUSDT", "quoteVolume": "1e9", "lastPrice": str(price)}]
        candles = candles_from(signal_closes[0], signal_closes[1])
        with mock.patch.object(data, "tickers_24h", return_value=tickers), \
             mock.patch.object(data, "fear_greed", return_value=50), \
             mock.patch.object(data, "trending_symbols", return_value=set()), \
             mock.patch.object(data, "klines", side_effect=lambda s, i=None, l=250:
                               candles_from(uptrend(120)) if s == "BTCUSDT" else candles):
            main.cycle(state, PaperBroker(state))

    def test_buy_then_stop_out(self):
        closes = uptrend()
        closes[-1] = max(closes[-21:-1]) * 1.005
        vols = [100] * len(closes)
        vols[-1] = 500
        state = main.load_state()
        state["mode"] = "paper"
        self.run_cycle(state, closes[-1], (closes, vols))
        self.assertIn("XUSDT", state["positions"])
        pos = state["positions"]["XUSDT"]
        # Never risk more than ~1% of equity (plus fees) on the stop.
        self.assertLessEqual(pos["cost"] * (1 - pos["stop"] / pos["entry"]), 100 * config.RISK_PER_TRADE * 1.05)

        self.run_cycle(state, pos["stop"] * 0.99, (closes, vols))
        self.assertEqual(state["positions"], {})
        self.assertEqual(state["trades"][-1]["why"], "stop")
        self.assertLess(state["trades"][-1]["pnl"], 0)
        self.assertGreater(state["cash"], 97)

    def test_trailing_stop_locks_profit(self):
        state = {"mode": "paper", "positions": {}, "trades": [], "cooldown": {}, "cash": 80.0}
        state["positions"]["XUSDT"] = {"qty": 20, "cost": 20, "entry": 1.0, "atr": 0.02, "highest": 1.0,
                                      "stop": 0.96, "opened": int(time.time()), "reason": "t"}
        broker = PaperBroker(state)
        main.manage_positions(state, broker, {"XUSDT": 1.10})
        self.assertGreater(state["positions"]["XUSDT"]["stop"], 1.0)
        main.manage_positions(state, broker, {"XUSDT": 1.05})
        self.assertEqual(state["trades"][-1]["why"], "stop")
        self.assertGreater(state["trades"][-1]["pnl"], 0)

    def test_drawdown_halts(self):
        state = {"positions": {}, "start_equity": 100, "peak_equity": 100}
        self.assertEqual(main.risk_gate(state, 65), "halted")
        self.assertTrue(state["halted"])
        self.assertEqual(main.risk_gate(state, 120), "halted")


if __name__ == "__main__":
    unittest.main()
