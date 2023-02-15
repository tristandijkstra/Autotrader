import requests
import math
import pandas as pd
from datetime import datetime, timedelta
from binance.exceptions import BinanceAPIException
from time import sleep
import logging

log = logging.getLogger("bot")


def getOrderBook(symbol: str, limit: int = 100):
    r = requests.get(
        f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit={limit}"
    )
    return r.json()


def getTradeFee(client, summary: bool = False) -> float:
    """get trading fee

    Args:
        summary (bool, optional): set true to have fee printed. Defaults to False.

    Returns:
        float: trading fee in ratio
    """
    tfcall = client.get_trade_fee(symbol="XLMBTC")
    fee = max([tfcall[0]["makerCommission"], tfcall[0]["takerCommission"]])
    if summary:
        log.info(f"Fee: {fee}")

    return float(fee)


def sellOrder(
    client,
    portfolio,
    ticker: str,
    quantity: float,
    market: bool = False,
    price=None,
):
    """Create sell order

    Args:
        ticker (str): ticker to create sell order on
        quantity (float): amount of coin to sell
        base (str, optional): the base currency like BTC. Defaults to base.
        market (bool, optional): if true performs a market trade, otherwise limit. Defaults to True.
        price (float, optional): price to sell at for limit sales. Defaults to None.
    """
    assert portfolio is not None, "No portfolio data given"
    assert portfolio.bought, "Sell order failed: already sold"

    priceOriginal = price
    
    info = client.get_symbol_info(ticker)
    step_size = float(info["filters"][2]["stepSize"])
    minQty = float(info["filters"][2]["minQty"])
    precision = int(round(-math.log(step_size, 10), 0))
    
    quantity = "{:0.0{}f}".format(float(quantity), precision)
    price = "{:0.0{}f}".format(float(price), 8)
    
    assert float(quantity) > minQty, "Sell quantity too low"
    assert (
        abs(float(price) / priceOriginal) - 1 < 0.001
    ), "Price precision error: price > 0.1percent diff"


    log.info(f"Selling: {quantity} {ticker} at {price}: ")

    if market:
        order = client.order_market_sell(symbol=ticker, quantity=quantity)
        # log.info(order)
    elif market != True and price is not None:
        order = client.order_limit_sell(symbol=ticker, quantity=quantity, price=price)
        # log.info(order)
    else:
        log.error("Sell order failed: incorrect parameters")
        log.error(f"Price={price}, Ticker={ticker}, Quantity={quantity}")
        raise Exception()


    return order


def buyOrder(
    client,
    portfolio,
    ticker: str,
    quantity: float,
    market: bool = False,
    price=None,
):
    """Create buy order

    Args:
        ticker (str): ticker to create buy order on
        quantity (float): amount of coin to buy
        base (str, optional): the base currency like BTC. Defaults to base.
        market (bool, optional): if true performs a market trade, otherwise limit. Defaults to True.
        price (float, optional): price to buy at for limit sales. Defaults to None.
    """
    assert portfolio is not None, "No portfolio data given"
    assert not portfolio.bought, "Buy order failed: already bought"

    priceOriginal = price
    info = client.get_symbol_info(ticker)
    step_size = float(info["filters"][2]["stepSize"])
    minQty = float(info["filters"][2]["minQty"])
    precision = int(round(-math.log(step_size, 10), 0))

    quantity = "{:0.0{}f}".format(float(quantity) / float(price), precision)
    price = "{:0.0{}f}".format(float(price), 8)

    assert float(quantity) > minQty, "Buy quantity too low"
    assert (
        abs(float(price) / priceOriginal) - 1 < 0.001
    ), "Price precision error: price > 0.1percent diff"



    log.info(f"Buying: {quantity} {ticker} at {price}: ")
    if market:
        order = client.order_market_buy(symbol=ticker, quantity=quantity)
        # log.info(order)
    elif market != True and price is not None:
        order = client.order_limit_buy(symbol=ticker, quantity=quantity, price=price)
        # log.info(order)
    else:
        log.error("Buy order failed: incorrect parameters")
        log.error(f"Price={price}, Ticker={ticker}, Quantity={quantity}")
        raise Exception()

    return order


def findLevel(pricesWS, buying: bool, ticker: str, amount: float) -> float:
    """Finds buy price for limit order. Works for buying and selling. Performance: ~550-650 ms

    Args:
        buying (bool): Are you buying or selling
        ticker (str): ticker i.e.: XLMBTC
        price (float): price of coin
        amount (float): amount of coin in portfolio

    Returns:
        (float): price to set limit order at
    """
    amountMargin = 1.1
    maxLevels = 10

    oBook = getOrderBook(ticker, maxLevels)  # 300 ms

    currentPrice = float(pricesWS.liveData[ticker])

    if buying:
        asks = pd.DataFrame(oBook["asks"], dtype=float)

        asks["sum"] = asks.iloc[:, 1].cumsum() * currentPrice  # in basecoin
        asks["wavg"] = (asks.iloc[:, 1] * asks.iloc[:, 0]).cumsum() / asks.iloc[
            :, 1
        ].cumsum()

        BuyPrice = (asks[asks["sum"] > amountMargin * amount].iloc[0, :])[0]
        avgBuyPrice = (asks[asks["sum"] > amountMargin * amount].iloc[0, :])["wavg"]

        loss = round(avgBuyPrice / currentPrice * 100 - 100, 3)
        if abs(loss) > 0.05:
            log.info(
                f"Slip Loss = {loss}%, currentPrice = {currentPrice}, avgBuyPrice = {round(avgBuyPrice,8)}, BuyPrice = {BuyPrice}"
            )

        return BuyPrice, abs(loss)
    else:
        bids = pd.DataFrame(oBook["bids"], dtype=float)

        bids["sum"] = bids.iloc[:, 1].cumsum()  # in tradecoin
        bids["wavg"] = (bids.iloc[:, 1] * bids.iloc[:, 0]).cumsum() / bids.iloc[
            :, 1
        ].cumsum()

        SP = (bids[bids["sum"] > amountMargin * amount].iloc[0, :])[0]
        avgSP = (bids[bids["sum"] > amountMargin * amount].iloc[0, :])["wavg"]

        loss = round(avgSP / currentPrice * 100 - 100, 3)
        if abs(loss) > 0.05:
            log.info(
                f"Slip Loss = {loss}%, currentPrice = {currentPrice}, avgSP = {round(avgSP,5)}, SP = {SP}"
            )

        return SP, abs(loss)


def tradesequence(client, pricesWS, buying, ticker, amount, portfolio):
    maxTradeTime = 2.0 # seconds
    amount = amount * (0.999)

    if buying:
        price, slipLoss = findLevel(pricesWS, buying, ticker, amount)
        amount = amount * (0.996)

        try:
            order = buyOrder(
                client, portfolio, ticker, amount, market=False, price=price
            )
        except BinanceAPIException as e:
            if hasattr(e, "code"):
                if e.code == -2010:
                    log.error(f"Insufficient balance error: {e}")
                    return False, None, None, None, "Insuff balance", slipLoss
                else:
                    log.error(e)
                    return False, None, None, None, "Other Error", slipLoss

        except Exception as e:
            if hasattr(e, "message"):
                log.error(e.message)
            else:
                log.error(e)
            return False, None, None, None, "Other Error", slipLoss

        startTimeT = datetime.now()
        orderID = order["orderId"]
        while (datetime.now() - startTimeT).seconds < maxTradeTime:
            # FUTURE FEATURE LOOP FUNCTION
            sleep(0.5)

        if client.get_order(symbol=ticker, orderId=orderID)["status"] == "FILLED":
            return True, amount, price, orderID, False, slipLoss
        else:
            client.cancel_order(symbol=ticker, orderId=orderID)
            log.warning("Trade took too long")
            return False, None, None, None, "Slow to trade", slipLoss

    
    else:
        price, slipLoss = findLevel(pricesWS, buying, ticker, amount)

        try:
            order = sellOrder(
                client, portfolio, ticker, amount, market=False, price=price
            )
        except BinanceAPIException as e:
            if hasattr(e, "code"):
                if e.code == -2010:
                    log.error(f"Insufficient balance error: {e}")
                    return False, None, None, None, "Insuff balance", slipLoss
                else:
                    log.error(e)
                    return False, None, None, None, "Other Error", slipLoss
        except Exception as e:
            if hasattr(e, "message"):
                log.error(e.message)
            else:
                log.error(e)
            return False, None, None, None, "Other Error", slipLoss

        startTimeT = datetime.now()
        orderID = order["orderId"]
        while (datetime.now() - startTimeT).seconds < maxTradeTime:
            # FUTURE FEATURE LOOP FUNCTION
            sleep(0.5)
        if client.get_order(symbol=ticker, orderId=orderID)["status"] == "FILLED":
            return True, amount, price, orderID, False, slipLoss
        else:
            client.cancel_order(symbol=ticker, orderId=orderID)
            log.warning("Trade took too long")
            return False, None, None, None, "Slow to trade", slipLoss
