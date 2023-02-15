from CryptoBotV1.cryptobot import mainLoop
from CryptoBotV1 import misc
from extraction import extract

from strategies.hvs import hvBuy, hvSell

import logging
import logging.config

logging.config.fileConfig("logging.conf")


base = "BTC"

coins = ["XLM", "ADA", "DOT", "IOTA", "XRP", "ETH",
         "LINK", "FIL", "CAKE", "NEO", "ICP", "ETC"]         


if __name__ == "__main__":
    timeRanges = ["1m","15m", "1h"]
    keys = r"keys/keys.txt"
    client = extract.readKeys(r"keys/keys.txt", testnet=False)
    log = logging.getLogger("bot")
    try:
        mainLoop(client, base, coins, timeRanges, hfBuy, hfSell, sinkLimit = 3, maxHoldMinutes = 60)
    except Exception as e:
        log.error(e)
    finally:
        exit()