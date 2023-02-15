from binance import ThreadedWebsocketManager
import pandas as pd
from datetime import datetime
import logging

log = logging.getLogger("ws")


def tsToDt(ts: int) -> datetime:
    """Turns timestamp from the klines object into datetime Objects
        Args:
            ts (int): timestamp
        Returns:
            datetime (datetime.datetime): datetime verstion of timestamp
        """
    return datetime.fromtimestamp(ts/1000)

class priceDataWS:
    def __init__(self, coins, intervals, base="BTC") -> None:
        self.coins = coins
        self.histData = {}
        self.liveData = {}
        self.updateCount = {"1m": 0, "15m": 0, "1h": 0}
        self.counter = 0
        self.updated = {"1m": False, "15m": False, "1h": False}
        self.getPrices(intervals, base)
        self.BNBPrice = 0
        self.basePrice = 0
        log.debug("PriceData websocket started")

    def getPrices(self, intervals, base):
        twm = ThreadedWebsocketManager()
        twm.start()

        def handle_socket_message(msg):
            self.counter += 1

            sym = msg["data"]["s"]
            m = msg["data"]["k"]
            interval = m["i"]

            if sym in ["BNBUSDT", f"{base}USDT"]:
                # BNB and base data
                if sym == "BNBUSDT":
                    self.BNBPrice = m["c"]
                elif sym == f"{base}USDT":
                    self.basePrice = m["c"]
            else:
                # Closed Historical Data
                # print(self.updateCount[interval])
                if m["x"] == True:
                    klines = [
                        [float(m["t"]) + 60000, m["o"], m["c"], m["l"], m["h"], m["v"]]
                    ]
                    columns = ["timestamp", "open", "high", "low", "close", "volume"]

                    P = pd.DataFrame(klines, columns=columns).astype("float")

                    P["datetime"] = P["timestamp"].apply(tsToDt)
                    P.set_index(pd.DatetimeIndex(P["datetime"]), inplace=True)
                    P.drop(["timestamp", "datetime"], inplace=True, axis=1)

                    self.histData[f"{sym}_{interval}"] = P
                    self.updateCount[interval] += 1

                    if self.updateCount[interval] == len(self.coins):
                        self.updated[interval] = True
                        self.updateCount[interval] = 0

                # Live Data
                elif interval == "1m":
                    self.liveData[sym] = m["c"]

        streams = []
        for interval in intervals:
            for coin in self.coins:
                streams.append(f"{coin.lower() + base.lower()}@kline_{interval}")

        # add BNB and base usd price
        streams.append(f"{('BNBUSDT'.lower())}@kline_1m")
        streams.append(f"{base.lower()}usdt@kline_1m")
        twm.start_multiplex_socket(callback=handle_socket_message, streams=streams)
