from binance.client import Client
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from copy import deepcopy
import pandas_ta as ta
from tqdm import tqdm as tqdm
import math
import sys


def runStrategy(dat:dict, coins:list, buyStrat, sellStrat, lowestInterval:str="1m", base:str="BTC", baseAmount:int=100, sinkLimit:int=40, maxHold:int=4*60, startTime=None, estSlip=0.001) -> pd.DataFrame:
    """Processes historical data trought strategy returning a trading data datafram

    Args:
        dat (dict): historical dat dataframe
        coins (list): list of coins to be traded
        buyStrat (function): buy strategy
        sellStrat (function): sell strategy
        lowestInterval (str, optional): lowest time interval, 1m, 15m etc. Defaults to "1m".
        base (str, optional): pair to trade with. Defaults to "BTC".
        baseAmount (int, optional): starting amount of pair coins 100 to see percentual gains. Defaults to 100.
        sinkLimit (int, optional): sink sell value if it goes lower sell. Defaults to 40.

    Returns:
        pd.DataFrame: tradeData, dataframe with all buy and sell data
    """
    if startTime is not None:
        for item in dat.keys():
            dat[item] = dat[item][dat[item].index > startTime - timedelta(minutes=180)]

    bought = False
    boughtCoin = ""
    tradingFee = 0.00075 # HELLO 
    estSlip = estSlip # HELLO
    strategyData = {}
    strategyData["buyNext"] = False
    baseAmount0 = baseAmount

    # Max time before selling
    maxTimeHeld = timedelta(minutes=maxHold)

    # Trade data format
    tradeData = pd.DataFrame(columns=["timestamp", 
                                      "close",
                                      "buying", 
                                      "ticker", 
                                      "coinAmount", 
                                      "baseAmount", 
                                      "profit", 
                                      "timeHeld",
                                      "strategy"])

    # Get timeset list in lowest interval
    timeTemp = [name for name in dat.keys() if lowestInterval in name]
    timeTemp15m = [name for name in dat.keys() if "15m" in name]
    timeTemp1h = [name for name in dat.keys() if "1h" in name]

    timeset = dat[timeTemp[0]].index
    timeset15m = dat[timeTemp15m[0]].index
    timeset1h = dat[timeTemp1h[0]].index

    
    index1h = 0 
    index15m = 0 
    for index, timestamp in enumerate(tqdm(timeset)):
        if index < 180:
            continue

        # basic variables
        while timeset1h[index1h] != timestamp.replace(microsecond=0, second=0, minute=0):
            index1h += 1

        while (timeset15m[index15m].hour != timestamp.hour) or (timeset15m[index15m].minute != (timestamp.minute - timestamp.minute%15)):
            index15m += 1

        for coin in coins:
            # Basic Variables
            ticker = coin + base
            data1m = dat[ticker+"_1m"]
            data15m = dat[ticker+"_15m"]
            data1h = dat[ticker+"_1h"]
            currentPrice = data1m["close"].iloc[index]
            

            # strategy buy
            if bought == False:
                buyNow, strategyData = buyStrat(data1m, data15m, data1h, strategyData, index, index15m, index1h)
                if buyNow:
                    bought = True
                    boughtCoin = ticker

                    if len(tradeData) > 0:
                        baseAmount = tradeData["baseAmount"].iloc[-1]
                        
                    coinAmount = (1-tradingFee-estSlip) * (baseAmount/currentPrice)
                    summData = {"timestamp":timestamp,
                                "close":currentPrice,
                                "buying": True,
                                "ticker":ticker, 
                                "coinAmount":coinAmount , 
                                "baseAmount":None,
                                "profit": None,
                                "timeHeld": None,
                                "strategy": strategyData["buyStrat"]
                                }
                    tradeData = tradeData.append(summData, ignore_index=True)
                    strategyData["buyTime"] = timestamp
                    break
                continue

            # strategy sell
            if bought and boughtCoin == ticker:
                # sink limit sell
                sellNow, strategyData = sellStrat(data1m, data15m, data1h, strategyData, index, index15m, index1h)
                sinkSell =  currentPrice / tradeData["close"].iloc[-1] < (1 - (sinkLimit/100))
                timeSell = (timestamp - strategyData["buyTime"] > maxTimeHeld)
                if sinkSell:
                    print("Emergency sell")
                    print(f"Current: {currentPrice} | last: {strategyData['lastBuy']}")
                    strategyUsed = "Sink Sell"
                elif timeSell:
                    strategyUsed = "Time Sell"
                else:
                    strategyUsed = strategyData["sellStrat"]

                
                # perform trade
                if (sellNow or sinkSell or timeSell):
                    bought = False

                    coinAmount = tradeData["coinAmount"].iloc[-1]
                    baseAmount = (1-tradingFee-estSlip) * (coinAmount * currentPrice)

                    if len(tradeData) < 2:
                        profit = (baseAmount/baseAmount0-1) * 100
                    else:
                        oldBaseAmount = tradeData["baseAmount"].iloc[-2]
                        profit = (baseAmount/oldBaseAmount-1) * 100

                    timeHeld = timestamp - tradeData["timestamp"].iloc[-1]

                    summData = {"timestamp": timestamp,
                                "close": currentPrice,
                                "buying": False,
                                "ticker": ticker,
                                "coinAmount": None,
                                "baseAmount": baseAmount,
                                "profit": profit,
                                "timeHeld": timeHeld,
                                "strategy": strategyUsed
                                }
                    tradeData = tradeData.append(summData, ignore_index=True)
                    break
                continue

    return tradeData