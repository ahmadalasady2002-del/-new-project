import math
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ["STRATEGY"] = "safe"  # most tests check the calm defaults

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


class TakeProfitTests(unittest.TestCase):
    def test_half_sold_at_target_rest_risk_free(self):
        state = {"positions": {}, "trades": [], "cooldown": {}, "cash": 70.0}
        state["positions"]["XUSDT"] = {"qty": 30, "cost": 30, "entry": 1.0, "atr": 0.05, "highest": 1.0,
                                      "stop": 0.95, "opened": int(time.time()), "reason": "t"}
        broker = PaperBroker(state)
        with mock.patch.object(config, "TAKE_PROFIT_PCT", 0.10):
            main.manage_positions(state, broker, {"XUSDT": 1.11})
            pos = state["positions"]["XUSDT"]
            self.assertAlmostEqual(pos["qty"], 15)
            self.assertAlmostEqual(pos["cost"], 15)
            self.assertGreater(pos["stop"], 1.0)
            self.assertEqual(state["trades"][-1]["why"], "tp")
            self.assertGreater(state["trades"][-1]["pnl"], 1.5)
            # Second touch of the target doesn't sell again; a drop exits the rest at break-even.
            main.manage_positions(state, broker, {"XUSDT": 1.12})
            self.assertEqual(len(state["trades"]), 1)
            main.manage_positions(state, broker, {"XUSDT": 0.99})
        self.assertNotIn("XUSDT", state["positions"])
        # Price gapped through the break-even stop, so the rest lost a little; the trade is still a win.
        self.assertGreater(sum(t["pnl"] for t in state["trades"]), 1.0)


def pump_candles(n=120, jump=1.04, vol_mult=6):
    """Sideways-up 15m chart that breaks out on a volume spike in the last candle."""
    closes = [1.0 * (1.0005 ** i) * (1 + 0.01 * math.sin(i / 2)) for i in range(n)]
    closes[-1] = max(closes[-13:-1]) * jump
    vols = [1000] * n
    vols[-1] = 1000 * vol_mult
    return candles_from(closes, vols)


class MemeTests(unittest.TestCase):
    def test_pump_detected_with_tag_bonus(self):
        plain = strategy.evaluate_momentum("XUSDT", pump_candles())
        tagged = strategy.evaluate_momentum("XUSDT", pump_candles(), ["new", "meme"])
        self.assertIsNotNone(plain)
        self.assertEqual(tagged.score - plain.score, 20)
        self.assertIn("new+meme pump", tagged.reason)

    def test_no_volume_no_signal(self):
        self.assertIsNone(strategy.evaluate_momentum("XUSDT", pump_candles(vol_mult=1.5)))

    def test_too_new_or_already_vertical(self):
        self.assertIsNone(strategy.evaluate_momentum("XUSDT", pump_candles(n=25)))
        c = pump_candles()
        for k in range(1, 5):
            for key in ("open", "close", "high", "low"):
                c[-k][key] *= 1.4 ** (5 - k) / 1.4 ** 4 * 1.4
        self.assertIsNone(strategy.evaluate_momentum("XUSDT", c))

    def test_meme_universe(self):
        tickers = [
            {"symbol": "PEPEUSDT", "quoteVolume": "5e7", "lastPrice": "1", "change": "0.02"},
            {"symbol": "ABCUSDT", "quoteVolume": "3e6", "lastPrice": "1", "change": "0.40"},
            {"symbol": "BTCUSDT", "quoteVolume": "1e9", "lastPrice": "1", "change": "0.01"},
            {"symbol": "WIFUSDT", "quoteVolume": "1e5", "lastPrice": "1", "change": "0.90"},
        ]
        with mock.patch.object(config, "MIN_QUOTE_VOLUME", 1_000_000):
            u = data.build_meme_universe(tickers, set(), {"PEPE", "WIF"})
        self.assertEqual(list(u), ["ABCUSDT", "PEPEUSDT"])  # BTC isn't hot, WIF too thin
        self.assertEqual(u["ABCUSDT"], ["gainer"])

    def test_new_listings_tracked_after_first_run(self):
        state = {}
        self.assertEqual(main.new_listings(state, [{"symbol": "OLDUSDT"}]), [])
        self.assertEqual(main.new_listings(state, [{"symbol": "OLDUSDT"}, {"symbol": "NEWUSDT"}]), ["NEWUSDT"])


if __name__ == "__main__":
    unittest.main()


class BacktestTests(unittest.TestCase):
    def test_pump_bought_and_profit_taken(self):
        from bot import backtest
        # Calm drift, then a breakout on huge volume that keeps running, then a dump.
        closes = [1.0 * (1.0005 ** i) * (1 + 0.01 * math.sin(i / 2)) for i in range(150)]
        breakout = max(closes[-12:]) * 1.04
        closes += [breakout * 1.03 ** k for k in range(8)] + [breakout * 0.8] * 20
        vols = [1000] * 150 + [8000] * 8 + [1000] * 20
        hist = {"XUSDT": candles_from(closes, vols)}
        with mock.patch.multiple(config, STRATEGY="meme", TAKE_PROFIT_PCT=0.10, TAKE_PROFIT_SHARE=0.5,
                                 MAX_ATR_PCT=0.15, STOP_ATR=2.5, TRAIL_START_ATR=2.0, MIN_STOP_PCT=0.04,
                                 MAX_STOP_PCT=0.12, RISK_PER_TRADE=0.03, MAX_POSITION_PCT=0.30):
            sim = backtest.run(hist, {"XUSDT": ["meme"]})
        whys = [t["why"] for t in sim.trades]
        self.assertIn("tp", whys)
        self.assertGreater(sim.cash, 100)
        self.assertEqual(sim.positions, {})
        self.assertIn("end balance", backtest.summary(sim, 100, 1, 1))

    def test_history_pages_until_start(self):
        now = int(time.time()) // 900 * 900
        pages = []

        def fake(path, params):
            end = params["end"] // 1000
            rows = [[str((end // 900 * 900 - k * 900) * 1000), "1", "1", "1", "1", "1", "1"] for k in range(1, 1001)]
            pages.append(end)
            return {"list": rows}

        with mock.patch.object(data, "bybit_public", side_effect=fake):
            h = data.history("X", "15m", 15)
        self.assertEqual(len(pages), 2)
        self.assertTrue(all(a["time"] < b["time"] for a, b in zip(h, h[1:])))
        self.assertGreaterEqual(h[0]["time"], now - 15 * 86400)
        self.assertLessEqual(h[-1]["time"] + 900, time.time())


class SweepTests(unittest.TestCase):
    def test_to_hourly_merges_four_candles(self):
        from bot import backtest
        base = 1_700_000_000 - 1_700_000_000 % 3600
        cs = [{"time": base + k * 900, "open": k + 1, "high": k + 2, "low": k + 0.5, "close": k + 1.5,
               "volume": 10} for k in range(8)]
        h = backtest.to_hourly(cs)
        self.assertEqual(len(h), 2)
        self.assertEqual((h[0]["open"], h[0]["high"], h[0]["low"], h[0]["close"], h[0]["volume"]),
                         (1, 5, 0.5, 4.5, 40))

    def test_overrides_restore_config(self):
        from bot import backtest
        before = config.MOMENTUM_VOL_MULT
        with backtest.overrides({"MOMENTUM_VOL_MULT": 99}):
            self.assertEqual(config.MOMENTUM_VOL_MULT, 99)
        self.assertEqual(config.MOMENTUM_VOL_MULT, before)


def listing_candles(hours, breakout_at=None, path=None):
    """1h candles from a listing: wild first 6h, then a calm range around 1.0."""
    t0 = 1_700_000_000 - 1_700_000_000 % 3600
    out = []
    for h in range(hours):
        if h < 6:
            p, hi, vol = 1.5, 3.0, 5000  # listing spike; must be ignored
        else:
            p = 1.0 + 0.02 * math.sin(h)
            hi, vol = p * 1.01, 1000
        if path and h in path:
            p = path[h]
            hi = p * 1.01
        if breakout_at == h:
            p, hi, vol = 1.2, 1.21, 5000
        out.append({"time": t0 + h * 3600, "open": p, "high": hi, "low": p * 0.99, "close": p, "volume": vol})
    return t0, out


class LottoTests(unittest.TestCase):
    def setUp(self):
        config.load("lotto")

    def tearDown(self):
        config.load("safe")

    def test_entry_after_first_day_on_breakout(self):
        from bot import lotto
        t0, cs = listing_candles(31, breakout_at=30)
        sig = lotto.evaluate("NEWUSDT", cs, t0 - 10 * 3600, cs[-1]["time"] + 3600)  # midnight-based date
        self.assertIsNotNone(sig)
        self.assertIn("lotto", sig.tags)
        self.assertAlmostEqual(sig.age_h, 31)
        t0, early = listing_candles(20, breakout_at=19)
        self.assertIsNone(lotto.evaluate("NEWUSDT", early, t0, early[-1]["time"] + 3600))
        t0, calm = listing_candles(31)
        self.assertIsNone(lotto.evaluate("NEWUSDT", calm, t0, calm[-1]["time"] + 3600))

    def test_ladder_trail_and_stop(self):
        from bot import lotto
        def c(p):
            return {"open": p, "high": p, "low": p, "close": p}
        pos = {"entry": 1.0, "highest": 1.0, "opened": 0}
        self.assertEqual(lotto.exits(pos, c(0.5), 10), [])  # -50% is inside the 60% stop
        self.assertEqual(lotto.exits(dict(pos), c(0.39), 10)[0][2], "stop")
        acts = lotto.exits(pos, c(3.2), 10)
        self.assertEqual([(round(s, 3), w) for s, _, w in acts], [(0.333, "x3")])
        acts = lotto.exits(pos, c(11), 10)
        self.assertEqual([w for _, _, w in acts], ["x10"])
        self.assertEqual(lotto.exits(pos, c(6), 10), [])  # 45% off the top: hold
        self.assertEqual(lotto.exits(pos, c(5.4), 10)[0][2], "trail")
        # After the first step there is no -60% stop, only the trail.
        pos2 = {"entry": 1.0, "highest": 1.0, "opened": 0}
        lotto.exits(pos2, c(3.5), 10)
        self.assertEqual(lotto.exits(pos2, c(1.7), 10)[0][2], "trail")

    def test_backtest_moonshot_pays_for_losers(self):
        from bot import backtest
        history, listed = {}, {}
        moon = {h: 1.2 * 1.08 ** (h - 30) for h in range(31, 70)}
        moon.update({h: moon[69] * 0.4 for h in range(70, 80)})
        for name, path in (("MOONUSDT", moon), ("DEADUSDT", {h: 0.3 for h in range(31, 80)}),
                           ("FLATUSDT", {})):
            t0, cs = listing_candles(80, breakout_at=30, path=path)
            for x in cs:
                x["volume"] *= 1e3  # enough daily dollar volume
            history[name], listed[name] = cs, t0
        sim = backtest.run_lotto(history, listed)
        whys = {t["why"] for t in sim.trades}
        self.assertTrue({"x3", "x10", "trail", "stop"} <= whys)
        self.assertGreater(sim.cash, 100)
        msg = backtest.lotto_message(sim, 100, "آخر 30 يوم", 3)
        self.assertIn("🚀 1 وصلت 10 أضعاف", msg)
        self.assertIn("MOON", msg)

    def test_live_buys_ticket_and_climbs_ladder(self):
        import tempfile
        sent = []
        t0, cs = listing_candles(31, breakout_at=30)
        state = {"mode": "paper", "positions": {}, "trades": [], "cooldown": {}, "cash": 100.0}
        tickers = [{"symbol": "NEWUSDT", "quoteVolume": "2e6", "lastPrice": "1.2"},
                   {"symbol": "OLDUSDT", "quoteVolume": "9e9", "lastPrice": "1"}]
        broker = PaperBroker(state)
        with mock.patch.object(data, "listing_time", side_effect=lambda s: t0 if s == "NEWUSDT" else 0), \
             mock.patch.object(data, "klines", return_value=cs), \
             mock.patch.object(main.time, "time", return_value=cs[-1]["time"] + 3600), \
             mock.patch.object(main.notify, "send", side_effect=sent.append):
            main.find_entries(state, broker, {"NEWUSDT": 1.2}, 100.0, tickers)
            self.assertTrue(state["positions"]["NEWUSDT"]["lotto"])
            self.assertAlmostEqual(state["positions"]["NEWUSDT"]["cost"], 7.0)
            self.assertIn("🎟", sent[-1])
            entry = state["positions"]["NEWUSDT"]["entry"]
            main.manage_positions(state, broker, {"NEWUSDT": entry * 3.1})
        self.assertIn("🎉", sent[-1])
        self.assertAlmostEqual(state["positions"]["NEWUSDT"]["cost"], 7.0 * 2 / 3)
        self.assertEqual(state["listed"], {"NEWUSDT": t0, "OLDUSDT": 0})


class TelegramCommandTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import threading
        from bot.telegram_bot import Commands
        self.tmp = tempfile.TemporaryDirectory()
        self.p = mock.patch.object(config, "STATE_FILE", Path(self.tmp.name) / "state.json")
        self.p.start()
        self.state = {"mode": "paper", "positions": {}, "trades": [], "cooldown": {}, "cash": 70.0,
                      "start_equity": 100.0, "day_start_equity": 95.0}
        self.state["positions"]["PEPEUSDT"] = {"qty": 30, "cost": 30, "entry": 1.0, "atr": 0.05, "highest": 1.0,
                                              "stop": 0.9, "opened": int(time.time()), "reason": "t"}
        self.cmd = Commands(self.state, PaperBroker(self.state), threading.Lock())
        self.tickers = mock.patch.object(data, "tickers_24h", return_value=[
            {"symbol": "PEPEUSDT", "lastPrice": "1.2", "quoteVolume": "1"}])
        self.tickers.start()
        self.sent = []
        self.ns = mock.patch.object(main.notify, "send", side_effect=self.sent.append)
        self.ns.start()

    def tearDown(self):
        self.p.stop()
        self.tickers.stop()
        self.ns.stop()
        self.tmp.cleanup()

    def test_status_via_button(self):
        r = self.cmd.handle("📊 الحالة")
        self.assertIn("الرصيد: 106.00$", r)
        self.assertIn("PEPE: +20.0%", r)

    def test_pause_blocks_buying_and_resume(self):
        self.cmd.handle("⏸ وگف الشراء")
        self.assertEqual(main.risk_gate(self.state, 100), "paused from Telegram")
        self.assertTrue(config.STATE_FILE.exists())
        self.cmd.handle("/resume")
        self.assertIsNone(main.risk_gate(self.state, 100))

    def test_sellall_needs_confirmation(self):
        self.assertIn("/sellall yes", self.cmd.handle("/sellall"))
        self.assertIn("PEPEUSDT", self.state["positions"])
        self.assertIn("✅", self.cmd.handle("/sellall yes"))
        self.assertEqual(self.state["positions"], {})
        self.assertEqual(self.state["trades"][-1]["why"], "manual")
        self.assertIn("بطلبك", self.sent[-1])

    def test_plain_arabic_requests(self):
        with mock.patch.object(self.cmd, "test", return_value="T") as t, \
             mock.patch.object(self.cmd, "mode", return_value="M") as m:
            self.assertEqual(self.cmd.handle("جرب وضع اليانصيب"), "T")
            t.assert_called_with("lotto")
            self.assertEqual(self.cmd.handle("🎟 اختبار اليانصيب"), "T")
            self.assertEqual(self.cmd.handle("حول البوت لليانصيب"), "M")
            m.assert_called_with("lotto")

    def test_plain_arabic_questions(self):
        self.assertIn("الرصيد", self.cmd.handle("كم المبلغ الحالي"))
        self.assertIn("📜", self.cmd.handle("شنو الصفقات اللي سويتها"))

    def test_trades_and_unknown_and_mode_validation(self):
        self.assertIn("ما سوى", self.cmd.handle("📜 الصفقات"))
        self.assertIn("/help", self.cmd.handle("هلو"))
        self.assertIn("/mode lotto", self.cmd.handle("/mode banana"))
        self.assertIn("أوامر البوت", self.cmd.handle("/start"))

    def test_only_owner_chat_is_obeyed(self):
        from bot import telegram_bot
        batches = [
            {"result": [{"update_id": 5}]},  # backlog marker, skipped
            {"result": [{"update_id": 6, "message": {"chat": {"id": 111}, "text": "/sellall"}},
                        {"update_id": 7, "message": {"chat": {"id": 999}, "text": "/status"}}]},
        ]

        def fake_api(method, payload, timeout=10):
            if not batches:
                raise KeyboardInterrupt  # end the loop
            return batches.pop(0)

        with mock.patch.object(config, "TELEGRAM_CHAT_ID", "999"), \
             mock.patch.object(telegram_bot.notify, "api", side_effect=fake_api):
            with self.assertRaises(KeyboardInterrupt):
                self.cmd.run()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("📊", self.sent[0])
        self.assertIn("PEPEUSDT", self.state["positions"])  # the stranger's /sellall did nothing


class RateLimitTests(unittest.TestCase):
    def test_bybit_rate_limit_is_retried(self):
        replies = [{"retCode": 10006, "retMsg": "Too many visits"}, {"retCode": 0, "result": {"ok": 1}}]
        with mock.patch.object(data, "get_json", side_effect=lambda *a, **k: replies.pop(0)), \
             mock.patch.object(data.time, "sleep"):
            self.assertEqual(data.bybit_public("/x", {}), {"ok": 1})

    def test_other_errors_fail_fast(self):
        with mock.patch.object(data, "get_json", return_value={"retCode": 10001, "retMsg": "bad symbol"}):
            with self.assertRaises(RuntimeError):
                data.bybit_public("/x", {})


BINANCE_PAGE = {"code": "000000", "data": {"catalogs": [{"catalogId": 48, "articles": [
    {"id": 101, "code": "a1", "title": "Binance Will List Lombard (BARD) with Seed Tag Applied", "releaseDate": 1},
    {"id": 100, "code": "a0", "title": "Notice on New Trading Pairs & Trading Bots Services on Binance Spot"},
    {"id": 99, "code": "z9", "title": "Binance Futures Will Launch USDⓈ-Margined FOOUSDT Perpetual Contract"},
]}]}}
UPBIT_PAGE = {"success": True, "data": {"notices": [
    {"id": 5001, "title": "Lombard(BARD) 신규 거래지원 안내 (KRW, BTC, USDT 마켓)", "listed_at": "x"},
    {"id": 5000, "title": "[점검] 입출금 일시 중단 안내", "listed_at": "x"},
]}}


class AnnounceTests(unittest.TestCase):
    def test_parse_listing_headlines(self):
        from bot import announce
        self.assertEqual(announce.listing_coins("binance", "Binance Will List Lombard (BARD) with Seed Tag"), ["BARD"])
        self.assertEqual(announce.listing_coins("binance", "Binance Will List Two Prix (2Z) and Zama (ZAMA)"),
                         ["2Z", "ZAMA"])
        self.assertEqual(announce.listing_coins("binance", "Binance Alpha Will List Foo (FOO)"), [])
        self.assertEqual(announce.listing_coins("upbit", UPBIT_PAGE["data"]["notices"][0]["title"]), ["BARD"])
        self.assertEqual(announce.listing_coins("upbit", "[점검] 입출금 (BARD)"), [])
        titles = [t for _, t in [(a["id"], a["title"]) for a in announce.find_articles(BINANCE_PAGE)]]
        self.assertEqual(len(titles), 3)

    def test_exits(self):
        from bot import announce
        pos = {"entry": 1.0, "highest": 1.0, "opened": 0}
        self.assertIsNone(announce.exits(pos, 1.03, 10))
        self.assertIsNone(announce.exits(pos, 1.30, 10))
        self.assertEqual(announce.exits(pos, 1.19, 10), "trail")  # 8.5% off the 1.30 top
        self.assertEqual(announce.exits({"entry": 1.0, "highest": 1.0, "opened": 0}, 0.91, 10), "stop")
        self.assertEqual(announce.exits({"entry": 1.0, "highest": 1.0, "opened": 0}, 1.0, 7 * 3600), "time")

    def make_watcher(self, pages):
        import tempfile
        import threading
        from bot import announce
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(config, "STATE_FILE", Path(self.tmp.name) / "state.json")
        p.start()
        self.addCleanup(p.stop)
        state = {"mode": "paper", "positions": {}, "trades": [], "cooldown": {}, "cash": 100.0}
        w = announce.Watcher(state, PaperBroker(state), threading.Lock())
        self.sent = []
        pages.setdefault("upbit_markets", [{"market": "KRW-BTC"}, {"market": "BTC-ETH"}])

        def page(url, *a, **k):
            return pages["binance" if "binance" in url else "upbit_markets" if "api.upbit.com" in url else "upbit"]

        for target, kw in ((announce.data, {"get_json": page}),
                           (announce.notify, {"send": self.sent.append}),
                           (main.notify, {"send": self.sent.append})):
            for name, fn in kw.items():
                pm = mock.patch.object(target, name, side_effect=fn)
                pm.start()
                self.addCleanup(pm.stop)
        return w, state

    def test_first_read_is_old_news_then_new_listing_is_bought(self):
        pages = {"binance": BINANCE_PAGE, "upbit": UPBIT_PAGE}
        w, state = self.make_watcher(pages)
        with mock.patch.object(data, "price", return_value=2.0), \
             mock.patch.object(data, "klines", return_value=[{"open": 1.9}]):
            w.tick()
            self.assertEqual(state["positions"], {})  # old announcements never trigger a buy
            self.assertIn("BARD", w.report())
            pages["binance"] = {"data": {"articles": [
                {"id": 102, "title": "Binance Will List Zama (ZAMA)"}] + BINANCE_PAGE["data"]["catalogs"][0]["articles"]}}
            w.tick()
        pos = state["positions"]["ZAMAUSDT"]
        self.assertTrue(pos["ann"])
        self.assertAlmostEqual(pos["cost"], 20.0)
        self.assertIn("📢 Binance أعلنت", self.sent[-1])
        # The rally and the give-back are handled by the watcher, with Arabic reasons.
        with mock.patch.object(data, "price", return_value=2.6):
            w.manage()
        with mock.patch.object(data, "price", return_value=2.3):
            w.manage()
        self.assertEqual(state["positions"], {})
        self.assertGreater(state["trades"][-1]["pnl"], 0)
        self.assertIn("قفزت", self.sent[-1])

    def test_skips_coins_not_on_bybit_or_already_pumped(self):
        pages = {"binance": {"data": {"articles": []}}, "upbit": UPBIT_PAGE}
        w, state = self.make_watcher(pages)
        w.state["ann_seen"] = {"binance": [], "upbit": [], "upbit_markets": []}
        pages["binance"] = {"data": {"articles": [{"id": 1, "title": "Binance Will List Foo (FOO)"}]}}
        with mock.patch.object(data, "price", side_effect=RuntimeError("not on Bybit")):
            w.tick()
        self.assertIn("مو موجودة على Bybit", self.sent[-1])
        pages["binance"] = {"data": {"articles": [{"id": 2, "title": "Binance Will List Bar (BAR)"}]}}
        with mock.patch.object(data, "price", return_value=1.5), \
             mock.patch.object(data, "klines", return_value=[{"open": 1.0}]):
            w.tick()
        self.assertIn("تأخرنا", self.sent[-1])
        self.assertEqual(state["positions"], {})

    def test_new_upbit_krw_market_triggers_buy(self):
        pages = {"binance": BINANCE_PAGE, "upbit": UPBIT_PAGE}
        w, state = self.make_watcher(pages)
        with mock.patch.object(data, "price", return_value=2.0), \
             mock.patch.object(data, "klines", return_value=[{"open": 2.0}]):
            w.tick()
            pages["upbit_markets"] = pages["upbit_markets"] + [{"market": "KRW-NEWC"}, {"market": "BTC-OTHER"}]
            w.tick()
        self.assertEqual(list(state["positions"]), ["NEWCUSDT"])
        self.assertIn("أسواق Upbit", self.sent[-1])
        self.assertIn("آخر خبر قريته: Binance Will List Lombard", w.report())

    def test_big_market_list_is_not_replayed_as_news(self):
        markets = [{"market": f"KRW-C{i}"} for i in range(450)]
        pages = {"binance": BINANCE_PAGE, "upbit": UPBIT_PAGE, "upbit_markets": markets}
        w, state = self.make_watcher(pages)
        with mock.patch.object(data, "price", return_value=1.0) as price:
            for _ in range(3):
                w.tick()
        price.assert_not_called()
        self.assertEqual(self.sent, [])
        self.assertEqual(len(state["ann_seen"]["upbit_markets"]), 450)

    def test_burst_of_new_ids_resyncs_without_trading(self):
        pages = {"binance": BINANCE_PAGE, "upbit": UPBIT_PAGE, "upbit_markets": [{"market": "KRW-A"}]}
        w, state = self.make_watcher(pages)
        w.tick()
        pages["upbit_markets"] = [{"market": f"KRW-N{i}"} for i in range(10)]
        with mock.patch.object(data, "price", return_value=1.0) as price:
            w.tick()
            w.tick()
        price.assert_not_called()
        self.assertEqual(state["positions"], {})

    def test_broken_source_warns_once(self):
        pages = {"binance": {"weird": True}, "upbit": UPBIT_PAGE}
        w, _ = self.make_watcher(pages)
        w.tick()
        w.tick()
        warnings = [m for m in self.sent if "ما گدرت أقرا إعلانات Binance" in m]
        self.assertEqual(len(warnings), 1)
        self.assertIn("❌", w.report())
        self.assertIn("✅", w.report())
