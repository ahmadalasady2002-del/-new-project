"""Order execution: a paper broker for practice and a Bybit broker for real money."""
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import ROUND_DOWN, Decimal

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


class BybitError(Exception):
    pass


def _floor_to(value, step):
    """Round down to the exchange's step (e.g. 0.001) and format without float noise."""
    step = Decimal(step)
    return (Decimal(str(value)) / step).to_integral_value(ROUND_DOWN) * step


class BybitBroker:
    live = True
    RECV_WINDOW = "10000"

    def __init__(self, key, secret):
        if not key or not secret:
            raise BybitError("BYBIT_API_KEY / BYBIT_API_SECRET missing in .env")
        self.key, self.secret = key, secret
        self._filters = None

    def _request(self, method, path, params=None):
        params = params or {}
        ts = str(int(time.time() * 1000))
        if method == "GET":
            payload = urllib.parse.urlencode(params)
            url, body = f"{config.BYBIT_BASE}{path}?{payload}", None
        else:
            payload = json.dumps(params, separators=(",", ":"))
            url, body = f"{config.BYBIT_BASE}{path}", payload.encode()
        sig = hmac.new(self.secret.encode(), f"{ts}{self.key}{self.RECV_WINDOW}{payload}".encode(),
                       hashlib.sha256).hexdigest()
        req = urllib.request.Request(url, data=body, method=method, headers={
            "X-BAPI-API-KEY": self.key, "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": self.RECV_WINDOW, "X-BAPI-SIGN": sig,
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise BybitError(f"{e.code} {e.read().decode(errors='replace')}") from e
        if data.get("retCode") != 0:
            raise BybitError(f"{path}: {data.get('retCode')} {data.get('retMsg')}")
        return data["result"]

    def check_permissions(self):
        """Refuse to run with a key that can withdraw money."""
        info = self._request("GET", "/v5/user/query-api")
        perms = info.get("permissions", {})
        if any("Withdraw" in p for p in sum(perms.values(), [])):
            raise BybitError("This API key can WITHDRAW. Make a new key without the Withdrawal permission.")
        if str(info.get("readOnly")) == "1" or "SpotTrade" not in perms.get("Spot", []):
            raise BybitError("This API key cannot trade spot. Choose 'Read-Write' and tick Spot -> Trade.")

    def _symbol_filters(self, symbol):
        if self._filters is None:
            info = self._request("GET", "/v5/market/instruments-info", {"category": "spot"})
            self._filters = {
                s["symbol"]: {
                    "step": s["lotSizeFilter"]["basePrecision"],
                    "min_qty": float(s["lotSizeFilter"]["minOrderQty"]),
                    "min_notional": float(s["lotSizeFilter"].get("minOrderAmt", 5)),
                    "base": s["baseCoin"],
                }
                for s in info["list"]
            }
        return self._filters[symbol]

    def balance(self, coin):
        info = self._request("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": coin})
        for acct in info["list"]:
            for c in acct["coin"]:
                if c["coin"] == coin:
                    return max(0.0, float(c["walletBalance"] or 0) - float(c.get("locked") or 0))
        return 0.0

    def cash(self):
        return self.balance("USDT")

    def _filled(self, order_id):
        for _ in range(10):
            rows = self._request("GET", "/v5/order/history", {"category": "spot", "orderId": order_id})["list"]
            if rows and rows[0]["orderStatus"] in ("Filled", "PartiallyFilledCanceled", "Cancelled", "Rejected"):
                return rows[0]
            time.sleep(0.5)
        raise BybitError(f"order {order_id} did not finish")

    def buy(self, symbol, usdt, price):
        f = self._symbol_filters(symbol)
        usdt = float(_floor_to(min(usdt, self.cash()), "0.01"))
        if usdt < f["min_notional"]:
            return 0.0, 0.0
        res = self._request("POST", "/v5/order/create", {
            "category": "spot", "symbol": symbol, "side": "Buy", "orderType": "Market",
            "qty": f"{usdt:.2f}", "marketUnit": "quoteCoin",
        })
        order = self._filled(res["orderId"])
        qty = float(order["cumExecQty"])
        # Spot buy fees are taken from the coin received.
        fees = order.get("cumFeeDetail")
        qty -= float(fees.get(f["base"], 0)) if fees else float(order.get("cumExecFee") or 0)
        return max(qty, 0.0), float(order["cumExecValue"])

    def sell(self, symbol, qty, price):
        f = self._symbol_filters(symbol)
        qty = _floor_to(min(qty, self.balance(f["base"])), f["step"])
        if float(qty) < f["min_qty"] or float(qty) * price < f["min_notional"]:
            return 0.0
        res = self._request("POST", "/v5/order/create", {
            "category": "spot", "symbol": symbol, "side": "Sell", "orderType": "Market",
            "qty": format(qty, "f"), "marketUnit": "baseCoin",
        })
        order = self._filled(res["orderId"])
        fees = order.get("cumFeeDetail") or {"USDT": order.get("cumExecFee") or 0}
        return float(order["cumExecValue"]) - float(fees.get("USDT", 0))
