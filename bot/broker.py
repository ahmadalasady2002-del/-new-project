"""Order execution: a paper broker for practice and a Binance broker for real money."""
import hashlib
import hmac
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config


class PaperBroker:
    live = False

    def __init__(self, state):
        self.state = state
        state.setdefault("cash", config.PAPER_START_USDT)

    def cash(self):
        return self.state["cash"]

    def buy(self, symbol, usdt, price):
        usdt = min(usdt, self.state["cash"])
        qty = usdt * (1 - config.FEE_RATE) / price
        self.state["cash"] -= usdt
        return qty, usdt

    def sell(self, symbol, qty, price):
        proceeds = qty * price * (1 - config.FEE_RATE)
        self.state["cash"] += proceeds
        return proceeds


class BinanceError(Exception):
    pass


class BinanceBroker:
    live = True

    def __init__(self, key, secret):
        if not key or not secret:
            raise BinanceError("BINANCE_API_KEY / BINANCE_API_SECRET missing in .env")
        self.key, self.secret = key, secret
        self._filters = None

    def _request(self, method, path, params=None, signed=True):
        params = dict(params or {})
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 10000
            query = urllib.parse.urlencode(params)
            sig = hmac.new(self.secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            query += f"&signature={sig}"
        else:
            query = urllib.parse.urlencode(params)
        url = f"{config.BINANCE_BASE}{path}"
        data = None
        if method == "GET":
            url += f"?{query}"
        else:
            data = query.encode()
        req = urllib.request.Request(url, data=data, method=method, headers={"X-MBX-APIKEY": self.key})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise BinanceError(f"{e.code} {e.read().decode(errors='replace')}") from e

    def check_permissions(self):
        """Refuse to run with a key that can withdraw money."""
        info = self._request("GET", "/sapi/v1/account/apiRestrictions")
        if info.get("enableWithdrawals"):
            raise BinanceError("This API key can WITHDRAW. Make a new key with withdrawals disabled.")
        if not info.get("enableSpotAndMarginTrading"):
            raise BinanceError("This API key cannot trade. Enable 'Spot & Margin Trading'.")

    def _symbol_filters(self, symbol):
        if self._filters is None:
            info = self._request("GET", "/api/v3/exchangeInfo", {"permissions": "SPOT"}, signed=False)
            self._filters = {}
            for s in info["symbols"]:
                f = {x["filterType"]: x for x in s["filters"]}
                notional = f.get("NOTIONAL") or f.get("MIN_NOTIONAL") or {}
                self._filters[s["symbol"]] = {
                    "step": float(f["LOT_SIZE"]["stepSize"]),
                    "min_qty": float(f["LOT_SIZE"]["minQty"]),
                    "min_notional": float(notional.get("minNotional", 5)),
                    "base": s["baseAsset"],
                }
        return self._filters[symbol]

    def balance(self, asset):
        acct = self._request("GET", "/api/v3/account", {"omitZeroBalances": "true"})
        for b in acct["balances"]:
            if b["asset"] == asset:
                return float(b["free"])
        return 0.0

    def cash(self):
        return self.balance("USDT")

    def buy(self, symbol, usdt, price):
        usdt = math.floor(min(usdt, self.cash()) * 100) / 100
        if usdt < self._symbol_filters(symbol)["min_notional"]:
            return 0.0, 0.0
        order = self._request("POST", "/api/v3/order", {
            "symbol": symbol, "side": "BUY", "type": "MARKET",
            "quoteOrderQty": f"{usdt:.2f}", "newOrderRespType": "FULL",
        })
        base = self._symbol_filters(symbol)["base"]
        qty = float(order["executedQty"])
        qty -= sum(float(f["commission"]) for f in order.get("fills", []) if f["commissionAsset"] == base)
        return qty, float(order["cummulativeQuoteQty"])

    def sell(self, symbol, qty, price):
        f = self._symbol_filters(symbol)
        qty = min(qty, self.balance(f["base"]))
        qty = math.floor(qty / f["step"]) * f["step"]
        if qty < f["min_qty"] or qty * price < f["min_notional"]:
            return 0.0
        decimals = max(0, -int(math.floor(math.log10(f["step"]))))
        order = self._request("POST", "/api/v3/order", {
            "symbol": symbol, "side": "SELL", "type": "MARKET",
            "quantity": f"{qty:.{decimals}f}", "newOrderRespType": "FULL",
        })
        proceeds = float(order["cummulativeQuoteQty"])
        proceeds -= sum(float(x["commission"]) for x in order.get("fills", []) if x["commissionAsset"] == "USDT")
        return proceeds
