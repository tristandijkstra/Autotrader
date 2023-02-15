from binance.client import Client
from datetime import datetime, timedelta
import pandas as pd
from tqdm import tqdm as tqdm
import logging
import logging.config
import time

from . import misc
from . import account
from . import trade
from . import pricewebsocket
from extraction import extract

logging.config.fileConfig("logging.conf")
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 150)

# Remove dependance on this later
indicatorsDefault = ["EMA40", "EMA50", "EMA200", "RSI14", "MACD", "EMA500"]
indicators15 = ["EMA40"]
indicators1h = []
indicatorsDefault = ["EMA40", "EMA50", "EMA200", "RSI14", "MACD", "EMA500", "BBANDS20", "ZSCORE30", "SLOPE1"]
indicators15 = ["EMA40", "SLOPE1"]
indicators1h = []
indicatorsDefault = ["EMA40", "EMA50", "EMA200", "RSI14", "MACD", "EMA500", "BBANDS20", "ZSCORE30", "SLOPE15", "SLOPE5", "SLOPE1"]
indicators15 = ["EMA40", "SLOPE1"]
indicators1h = ["ZSCORE30"]


def mainLoop(client, base, coins, timeRanges, buyStrat, sellStrat, sinkLimit:int = 40, maxHoldMinutes:int = (60 * 4)):
    """Main loop of the bot

    Args:
        buyStrat (function): buyStrat function
        sellStrat (function): sellStrat function
        sinkLimit (int, optional): min percentage to stoploss. Defaults to 40.
        maxHoldMinutes (int, optional): max time to hold. Defaults to 12 hrs.
    """
    log = logging.getLogger("bot")
    log.debug("Starting bot")
    misc.awaitStart()
    startInitTime = datetime.now()
    tradingFee = trade.getTradeFee(client)
    strategyData = {}

    # Portfolio init
    portfolio = account.Portfolio(client, base, coins)
    portfolio.refresh(True)

    # Websocket init
    pricesWS = pricewebsocket.priceDataWS(coins, timeRanges, base)

    bought, coinBalanceBought, boughtCoin, coinTradeBalance, baseTradeBalance = portfolio.values

    # Max time before selling
    maxTimeHeld = timedelta(minutes=maxHoldMinutes)

    # Trade data format
    tradeData = pd.DataFrame(columns=["timestamp",
                                      "close",
                                      "buying",
                                      "ticker",
                                      "coinAmount",
                                      "baseAmount",
                                      "profit",
                                      "timeHeld",
                                      "strategy",
                                      "failed",
                                      "slip",
                                      "BNBAmount",
                                      "base"])

    dat = extract.initBotData(client, coins, ["1m"], base)
    dat15 = extract.initBotData(client, coins, ["15m"], base, hours=13)
    dath = extract.initBotData(client, coins, ["1h"], base, hours=20)
    dat.update(dat15)
    dat.update(dath)

    dat = extract.genIndicatorsMultiple(dat, "1m", indicatorsDefault)
    dat = extract.genIndicatorsMultiple(dat, "15m", indicators15)

    startTime = next(iter(dat.values())).iloc[-1].name.to_pydatetime()

    lastTime1m = next(iter(dat.values())).iloc[-1].name.to_pydatetime()
    lastTime15m = next(iter(dat15.values())).iloc[-1].name.to_pydatetime()
    lastTime1h = next(iter(dath.values())).iloc[-1].name.to_pydatetime()

    misc.saveMarketData(dat, coins, base)
    endInitTime = (datetime.now() - startInitTime)

    # buy time, base amount and buy price for last trades
    strategyData["buyTime"], strategyData["lastBaseAmount"], strategyData["lastBuy"] = misc.loadSaveData()

    log.debug(f"Total init time = {endInitTime.seconds} {endInitTime.microseconds/1000} ms")
    log.debug(f"Last 1m: {lastTime1m}")
    log.debug(f"Last 15m: {lastTime15m}")
    log.debug(f"Last 1h: {lastTime1h}")
    log.debug(f"Start Time: {startTime}")

    log.debug(f"Trading fee: {tradingFee*100}%")


    loops = 0
    mins = 0
    nTrades = 0
    nTradesMinute = 0
    # Perhaps make this a parameter later:
    maxTradesPerMinute = 2

    while True:
        time.sleep(0.010)

        timeDiffSeconds = (datetime.now() - lastTime1m).seconds
        lightDesync = timeDiffSeconds > 60
        heavyDesync = timeDiffSeconds > 70
        # if lightDesync:
        #     log.warning(f"Light Desync: {timeDiffSeconds}, {datetime.now()}, {lastTime1m}")
        if heavyDesync:
            log.warning(f"Heavy Desync: {timeDiffSeconds}, {datetime.now()}, {lastTime1m}")

        # 1 minute update
        if pricesWS.updated["1m"]:
            datTemp = misc.getLatestDataV2(pricesWS, dat, "1m", coins, base)
            dat = extract.genIndicatorsMultiple(datTemp, "1m", indicatorsDefault)
            minsBought = int((datetime.now() - strategyData["buyTime"]).seconds / 60) if bought else "-"
            misc.saveMarketData(dat, coins, base)
            log.info(f"m{mins}, 1min UPDATE, bought: {bought}, boughtCoin: {boughtCoin}, #trades: {nTrades}, minsBought: {minsBought}/{maxHoldMinutes}")
            mins += 1
            lastTime1m += timedelta(0, 60)
            nTradesMinute = 0


        # 15 minute update
        if pricesWS.updated["15m"]:
            datTemp = misc.getLatestDataV2(pricesWS, dat, "15m", coins, base)
            dat = extract.genIndicatorsMultiple(datTemp, "15m", indicators15)
            log.info(f"m{mins}, 15min UPDATE")
            if bought:
                log.info(dat[f"{boughtCoin}{base}_1m"].tail())
            else:
                log.info(dat[f"{coins[0]}{base}_1m"].tail())
            lastTime15m += timedelta(0, 60*15)

        # 1 hour update
        if pricesWS.updated["1h"]:
            datTemp = misc.getLatestDataV2(pricesWS, dat, "1h", coins, base)
            dat = extract.genIndicatorsMultiple(datTemp, "1h", indicators1h)
            log.info(f"m{mins}, 1h UPDATE")
            lastTime1h += timedelta(0, 60*60)
    

        if (mins > 0) and not (pricesWS.updated["1m"] or heavyDesync or (nTradesMinute > maxTradesPerMinute)):
            loops += 1
            timestamp = datetime.now()
            ### STRATEGY HERE
            for coin in coins:
                # Basic Variables
                ticker = coin + base
                data1m = dat[ticker+"_1m"]
                data15m = dat[ticker+"_15m"]
                data1h = dat[ticker+"_1h"]
                currentPrice = data1m["close"].iloc[-1]

                # strategy buy
                if bought == False:
                    buyNow, strategyData = buyStrat(
                        data1m, data15m, data1h, strategyData)
                    if buyNow:
                        log.info("Buying point found")
                        baseTradeBalance = portfolio.baseTradeBalance
                        tseqStatus, _, _, _, FailMessage, slipLoss = trade.tradesequence(client, pricesWS, True, ticker, baseTradeBalance, portfolio)
                        portfolio.refresh()
                        bought, coinBalanceBought, boughtCoin, coinTradeBalance, _ = portfolio.values
                        coinAmount = portfolio.coinTradeBalance

                        summData = {"timestamp": timestamp,
                                    "close": currentPrice,
                                    "buying": True,
                                    "ticker": ticker,
                                    "coinAmount": coinAmount,
                                    "baseAmount": None,
                                    "profit": None,
                                    "timeHeld": None,
                                    "strategy": strategyData["buyStrat"],
                                    "failed": FailMessage,
                                    "slip": slipLoss,
                                    "BNBAmount":portfolio.BNBamount,
                                    "base": base,
                                    }
                        
                        nTradesMinute += 1
                        if tseqStatus:
                            strategyData["buyTime"] = timestamp
                            strategyData["lastBaseAmount"] = baseTradeBalance
                            nTrades += 0.5
                            misc.storeSaveData(timestamp, baseTradeBalance, strategyData["lastBuy"])

                        tradeData = tradeData.append(summData, ignore_index=True)
                        misc.logTradeData(tradeData, startTime, not tseqStatus)
                        break
                    continue


                # strategy sell
                if bought and boughtCoin == coin:

                    sinkSell = (currentPrice / strategyData["lastBuy"]) < (1 - (sinkLimit/100))
                    timeSell = (timestamp - strategyData["buyTime"] > maxTimeHeld)

                    sellNow, strategyData = sellStrat(data1m, data15m, data1h, strategyData)

                    if sinkSell:
                        log.info("Emergency sell")
                        log.debug(f"Current: {currentPrice} | last: {strategyData['lastBuy']}")
                        strategyUsed = "Sink Sell"
                    elif timeSell:
                        log.info(f"Time sell {maxHoldMinutes} elapsed")
                        strategyUsed = "Time Sell"
                    else:
                        
                        strategyUsed = strategyData["sellStrat"]

                    if sellNow:
                        log.debug("Selling point found")

                    # perform trade
                    if (sellNow or sinkSell or timeSell):
                        log.debug("sellNow or sinkSell or timeSell")
                        coinAmount = portfolio.coinTradeBalance
                        tseqStatus, tseqAmount, tseqPrice_, _, FailMessage, slipLoss = trade.tradesequence(client, pricesWS, False, ticker, coinTradeBalance, portfolio)
                        portfolio.refresh()
                        bought, coinBalanceBought, boughtCoin, coinTradeBalance, baseTradeBalance = portfolio.values
                        baseTradeBalance = portfolio.baseTradeBalance
                        
                        timeHeld = timestamp - strategyData["buyTime"]

                        profit = ((baseTradeBalance / strategyData["lastBaseAmount"]) - 1 - abs(tradingFee*2)) * 100 

                        summData = {"timestamp": timestamp,
                                    "close": tseqPrice_,
                                    "buying": False,
                                    "ticker": ticker,
                                    "coinAmount": None,
                                    "baseAmount": baseTradeBalance ,
                                    "profit": profit,
                                    "timeHeld": timeHeld,
                                    "strategy": strategyUsed,
                                    "failed": FailMessage,
                                    "slip": slipLoss,
                                    "BNBAmount":portfolio.BNBamount,
                                    "base": base,
                                    }
                        tradeData = tradeData.append(summData, ignore_index=True)
                        misc.logTradeData(tradeData, startTime, not tseqStatus)

                        nTradesMinute += 1
                        if tseqStatus:
                            strategyData["lastBaseAmount"] = baseTradeBalance
                            misc.storeSaveData(timestamp, baseTradeBalance, strategyData["lastBuy"])
                            nTrades += 0.5
                        break
                    continue



if __name__ == "__main__":
    print("run from run file")
