from .misc import LockedError
import logging

log = logging.getLogger("bot")

class Portfolio():
    def __init__(self, client, base, coins) -> None:
        self.bought = 0
        self.boughtCoin = 0
        self.locked = 0
        self.lockedCoin = 0
        self.coinBalanceBought = 0
        self.coinBalanceLocked = 0
        self.baseTradeBalance = 0 
        self.baseBalanceLocked = 0 
        self.coinTradeBalance = 0
        self.BNBamount = 0
        self.values = 0
        self.client = client
        self.base = base
        self.coins = coins

    def refresh(self, summary:bool=False):
        # performance: ~2.6 seconds
        self.baseTradeBalance = float(self.client.get_asset_balance(asset=self.base)["free"])
        self.baseBalanceLocked = float(self.client.get_asset_balance(asset=self.base)["locked"])
        self.BNBamount = float(self.client.get_asset_balance(asset="BNB")["free"])

        self.coinBalance = {}
        self.coinBalanceLocked = {}
        self.coinBalanceBought = {}

        for coin in self.coins:
            balance = float(self.client.get_asset_balance(asset=coin)["free"])
            locked = float(self.client.get_asset_balance(asset=coin)["locked"])
            self.coinBalance[coin] = balance
            if balance > 0:
                self.coinBalanceBought[coin] = balance
                self.coinTradeBalance = balance
            if locked > 0:
                self.coinBalanceLocked[coin] = locked

        if round(self.baseTradeBalance, 4) == 0 or len(self.coinBalanceBought) != 0:
            self.bought = True
            self.boughtCoin = list(self.coinBalanceBought.keys())[0] # change later for multiple coins
        else:
            self.bought = False
            self.boughtCoin = None
        if len(self.coinBalanceLocked) != 0:
            self.locked = True
            self.lockedCoin = list(self.coinBalanceBought.keys())[0] # change later for multiple coins
            raise LockedError(f"Coin locked: {self.lockedCoin}")
        else:
            self.locked = False
            self.lockedCoin = None

        assert (len(self.coinBalanceBought) < 2), "More than 1 coin bought"

        if summary:
            log.debug(f"base amount: {self.baseTradeBalance} {self.base}, locked: {self.baseBalanceLocked} {self.base}")
            log.debug(f"BNB amount: {self.BNBamount}")
            log.debug(f"Coins free: {self.coinBalance}")
            log.debug(f"Coins locked: {self.coinBalanceLocked}")
            log.debug(f"Coins bought: {self.coinBalanceBought}")
            log.debug(f"bought status = {self.bought}, bought coin = {self.boughtCoin}")

        self.values = (self.bought, self.coinBalanceBought, self.boughtCoin, self.coinTradeBalance, self.baseTradeBalance)
