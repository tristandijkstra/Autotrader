import pandas as pd
import numpy as np
import random
import scipy.stats as ss
import scipy

# import BackTesterV2 as B2
from glob import glob
import os
import sys
from datetime import datetime
from binance.client import Client
import matplotlib.pyplot as plt
from datetime import timedelta

sys.path.append(".") # embarassing i know
import extraction.extract as gd
import BackTesterV3.main as m
from strategies import ns
from strategies import tradingview


def getTradeData(dateStart=None, dateEnd=None, foldername="logData", base="BTC"):
    tradeData = pd.DataFrame(
        columns=[
            "timestamp",
            "close",
            "buying",
            "ticker",
            "coinAmount",
            "baseAmount",
            "profit",
            "timeHeld",
            "strategy",
            "failed",
        ]
    )
    listOfFiles = glob(os.path.join(f"{foldername}/*0.csv"))
    for u in listOfFiles:
        P = pd.read_csv(u).iloc[:, 1::]
        P["timestamp"] = pd.to_datetime(P["timestamp"])
        tradeData = tradeData.append(P, ignore_index=True)

    tradeData = tradeData.drop_duplicates(subset=["timestamp", "close"])

    if dateStart is not None:
        tradeData = tradeData[tradeData["timestamp"] >= dateStart]
    if dateEnd is not None:
        tradeData = tradeData[tradeData["timestamp"] <= dateEnd]

    failedTrades = len(tradeData) - len(
        tradeData[tradeData["failed"].isin([False, "False"])]
    )

    tradeData = tradeData[tradeData["failed"].isin([False, "False"])]
    listOfCoins = tradeData["ticker"].unique()
    listOfCoins = [u.replace(base, "") for u in listOfCoins]
    tradeData = tradeData.sort_values(by=["timestamp"])

    # Remove Later
    if tradeData.iloc[0]["buying"] == False:
        tradeData = tradeData.iloc[1::]
        print("Removing first item")
    if tradeData.iloc[-1]["buying"] == True:
        tradeData = tradeData.iloc[0:-1:]
        print("Removing final item")

    baseAmount = tradeData.iloc[1]["baseAmount"]
    tradeData = tradeData.sort_values(by=["timestamp"])
    tradeData = tradeData.drop_duplicates(subset=["timestamp", "close"])

    return tradeData, listOfCoins, baseAmount, failedTrades


def runBacktester(
    start,
    end,
    coins,
    base,
    timeRanges,
    buyStrat,
    sellStrat,
    baseAmount,
    firstTrade,
    # saveFileIndicator,
    startMargin=timedelta(0, 900 * 60, 0),
    saveFolder="DiagnosticsV2/temp",
    reset=False,
):
    start = str((start - timedelta(0, start.second, start.microsecond) - startMargin))
    end = str(end)

    saveFileIndicator = f"{''.join(coins)}_{start.replace(' ','').replace('.','').replace(':','')}_{end}"[::3]

    keys = r"keys/keys.txt"
    client = gd.readKeys(keys)

    indicatorsDefault = [
        "EMA40",
        "EMA50",
        "EMA200",
        "RSI14",
        "MACD",
        "EMA500",
        "BBANDS20",
        "ZSCORE30",
        "SLOPE1",
    ]
    indicators15 = ["EMA40", "SLOPE1"]
    indicators1h = []

    dat = gd.generateBTData(
        saveFileIndicator,
        client,
        coins,
        base,
        timeRanges,
        start,
        end,
        saveFolder,
        False,
        True,
    )

    dat = gd.genIndicatorsMultiple(dat, "1m", indicatorsDefault)
    dat = gd.genIndicatorsMultiple(dat, "15m", indicators15)
    dat = gd.genIndicatorsMultiple(dat, "1h", indicators1h)

    if os.path.exists(f"{saveFolder}/BT_{saveFileIndicator}.csv") and not reset:
        print("Backtester results have already been generated")
        tradeData = pd.read_csv(f"{saveFolder}/BT_{saveFileIndicator}.csv").iloc[:, 1::]
        tradeData["timestamp"] = pd.to_datetime(tradeData["timestamp"])
        return dat, tradeData
    else:
        print(f"Generating BackTester results")
        tradeData = m.runStrategy(
            dat, coins, buyStrat, sellStrat, baseAmount=baseAmount, startTime=firstTrade, sinkLimit=6, maxHold=60
        )
        tradeData.to_csv(f"{saveFolder}/BT_{saveFileIndicator}.csv")

    return dat, tradeData


def plotResults(coins, priceData, btData, realData, start, end):
    def detailedView(coin, data, btData, realData, base="BTC"):
        btsellData = btData[btData["buying"] == False]
        btbuyData = btData[btData["buying"] == True]
        realsellData = realData[realData["buying"] == False]
        realbuyData = realData[realData["buying"] == True]

        fig, axs = plt.subplots(1, 1, sharex=True, num=f"{coin}{base}")
        temp = data[f"{coin}{base}_1m"]
        btsells = btsellData[btsellData["ticker"] == f"{coin}{base}"]
        btbuys = btbuyData[btbuyData["ticker"] == f"{coin}{base}"]
        realsells = realsellData[realsellData["ticker"] == f"{coin}{base}"]
        realbuys = realbuyData[realbuyData["ticker"] == f"{coin}{base}"]
        axs.plot(temp.index, temp["close"], label="close")
        axs.plot(temp.index, temp["EMA_200"], label="EMA_200")
        axs.plot(temp.index, temp["EMA_500"], label="EMA_500")

        axs.plot(
            btbuys["timestamp"],
            btbuys["close"],
            marker="^",
            color="orange",
            linestyle="none",
            label="bt buy"
        )
        axs.plot(
            btsells["timestamp"],
            btsells["close"],
            marker="^",
            color="indigo",
            linestyle="none",
            label="bt sell"
        )
        axs.plot(
            realbuys["timestamp"],
            realbuys["close"],
            marker=".",
            color="lime",
            linestyle="none",
            label="real buy"
        )
        axs.plot(
            realsells["timestamp"],
            realsells["close"],
            marker=".",
            color="red",
            linestyle="none",
            label="real sell"
        )

        axs.legend()
        axs.grid()
        axs.set_title(f"{coin} from {start.date()} to {end.date()}, {(end.date()-start.date()).days} days")

    for coin in coins:
        detailedView(coin, priceData, btData, realData)


def totalProfitGraph(btData, realData, baseAmount):
    fig, axs = plt.subplots(1, 1, sharex=True, num=f"Profits")
    btsellData = btData[btData["buying"] == False]
    btbuyData = btData[btData["buying"] == True]
    realsellData = realData[realData["buying"] == False]
    realbuyData = realData[realData["buying"] == True]
    axs.plot(
        realsellData["timestamp"],
        baseAmount * ((realsellData["profit"] / 100) + 1).cumprod(),
        label="real calculated (legacy)",
    )
    axs.plot(realsellData["timestamp"], realsellData["baseAmount"], label="real")
    axs.plot(btsellData["timestamp"], btsellData["baseAmount"], label="BackTester")
    axs.legend()


def plotBNB(realData):
    fig, axs = plt.subplots(1, 1, sharex=True, num=f"BNB")
    axs.plot(realData["timestamp"], realData["BNBAmount"], label="BNBAmount")
    axs.legend()


def textSummary(realData, btData, failedTrades, start, end, backtester=False):
    print(f"Failed transactions: {failedTrades}/{len(realData)+failedTrades}")
    print(f"Total succesfull transactions: real = {len(realData)/2} backtester = {len(btData)/2}")

    matchingBuys = 0
    matchingSells = 0
    loosematchingBuys = 0
    loosematchingSells = 0
    timeMatchingBuys = 0
    timeMatchingSells = 0

    btsellData = btData[btData["buying"] == False]
    btbuyData = btData[btData["buying"] == True]
    realsellData = realData[realData["buying"] == False]
    realbuyData = realData[realData["buying"] == True]

    for _, realTrade in realbuyData.iterrows():
        for _, btTrade in btbuyData.iterrows():
            if realTrade["ticker"] == btTrade["ticker"]:
                if abs(realTrade["timestamp"] - btTrade["timestamp"]) < timedelta(0, 5 * 60, 0):
                    matchingBuys += 1
                    timeMatchingBuys += 1
                if abs(realTrade["timestamp"] - btTrade["timestamp"]) < timedelta(0, 15 * 60, 0):
                    loosematchingBuys += 1
            else:
                if abs(realTrade["timestamp"] - btTrade["timestamp"]) < timedelta(0, 5 * 60, 0):
                    timeMatchingBuys += 1

    for _, realTrade in realsellData.iterrows():
        for _, btTrade in btsellData.iterrows():
            if realTrade["ticker"] == btTrade["ticker"]:
                if abs(realTrade["timestamp"] - btTrade["timestamp"]) < timedelta(0, 5 * 60, 0):
                    matchingSells += 1
                    timeMatchingSells += 1
                if abs(realTrade["timestamp"] - btTrade["timestamp"]) < timedelta(0, 15 * 60, 0):
                    loosematchingSells += 1
            else:
                if abs(realTrade["timestamp"] - btTrade["timestamp"]) < timedelta(0, 5 * 60, 0):
                    timeMatchingSells += 1

    print(f"Matching buys (5 mins): {matchingBuys}({round(matchingBuys/len(realbuyData)*100,0)}% | {round(matchingBuys/len(btbuyData)*100,0)}%), loose matches(15 mins): {loosematchingBuys}")
    print(f"Matching sells (5 mins): {matchingSells}({round(matchingSells/len(realsellData)*100,0)}% | {round(matchingSells/len(btsellData)*100,0)}%), loose matches(15 mins): {loosematchingSells}\n")

    print(f"Time matching buys (5 mins): {timeMatchingBuys}({round(timeMatchingBuys/len(realsellData)*100,0)}% | {round(timeMatchingBuys/len(btsellData)*100,0)}%)")
    print(f"Time matching sells (5 mins): {timeMatchingSells}({round(timeMatchingSells/len(realsellData)*100,0)}% | {round(timeMatchingSells/len(btsellData)*100,0)}%)")

    realwins = len(realsellData[realsellData["profit"] > 0])
    reallosses = len(realsellData[realsellData["profit"] < 0])
    btwins = len(btsellData[btsellData["profit"] > 0])
    btlosses = len(btsellData[btsellData["profit"] < 0])
    realTotal = len(realData) / 2
    btTotal = len(btData) / 2

    realTharp = ((realwins/ realTotal* realsellData[realsellData["profit"] > 0]["profit"].mean())
        + (reallosses/ realTotal* realsellData[realsellData["profit"] < 0]["profit"].mean())
    ) / (-realsellData[realsellData["profit"] < 0]["profit"].mean())

    btTharp = (
        (btwins / btTotal * btsellData[btsellData["profit"] > 0]["profit"].mean())
        + (btlosses / btTotal * btsellData[btsellData["profit"] < 0]["profit"].mean())
    ) / (-btsellData[btsellData["profit"] < 0]["profit"].mean())

    epochDuration = end - start
    epochDurationDays = int(epochDuration.days) if (int(epochDuration.days) != 0) else 1

    # Numberical performance
    realbiggestLossIndex = pd.to_numeric(realData["profit"]).argmin()
    realbiggestWinIndex = pd.to_numeric(realData["profit"]).argmax()
    realtradesPerDay = len(realsellData) / epochDurationDays
    btbiggestLossIndex = pd.to_numeric(btData["profit"]).argmin()
    btbiggestWinIndex = pd.to_numeric(btData["profit"]).argmax()
    bttradesPerDay = len(btsellData) / epochDurationDays

    print(f"First trade (Real | Backtester): {realData.iloc[0]['timestamp']} | {btData.iloc[0]['timestamp']}")
    print(f"Last trade (Real | Backtester): {realData.iloc[-1]['timestamp']} | {btData.iloc[-1]['timestamp']}")

    print("\n")

    print(f"Backtester trades: {len(btsellData)} | wins: {btwins} | losses: {btlosses} | winrate: {round(btwins/len(btsellData)*100,2)}%")
    print(f"Real trades: {len(realsellData)} | wins: {realwins} | losses: {reallosses} | winrate: {round(realwins/len(realsellData)*100,2)}%")
    if not backtester:
        slipData = realData["slip"]
        BNBData = realData["BNBAmount"]
        print(f"Slip (avg|median|min|max): {round(slipData.mean(),4)} | {round(slipData.median(),4)} | {slipData.min()} | {slipData.max()}")
        print(f"BNB (total | avg p trade): {round(BNBData.min()-BNBData.max(),8)} | {round((BNBData.min()-BNBData.max())/len(realData),8)}")
    
    print("\n")

    realTimeBetweenBuys = (
        realbuyData["timestamp"]
        .iloc[1::]
        .reset_index(drop=True)
        .sub(realbuyData["timestamp"].iloc[:-1:].reset_index(drop=True))
    ).tolist()
    btTimeBetweenBuys = (
        btbuyData["timestamp"]
        .iloc[1::]
        .reset_index(drop=True)
        .sub(btbuyData["timestamp"].iloc[:-1:].reset_index(drop=True))
    ).tolist()
    realMedianTBB = np.median(realTimeBetweenBuys)
    btMedianTBB = np.median(btTimeBetweenBuys)

    # btAvgTradeTime = btsellData['timeHeld'].sum()/len(btsellData)
    # realAvgTradeTime = realsellData['timeHeld'].sum()/len(realsellData)
    # btMedianTradeTime = pd.to_timedelta(np.median(sellData['timeHeld'].values))
    # realMedianTradeTime = pd.to_timedelta(np.median(sellData['timeHeld'].values))

    print(
        f"Median time between buys (Real | Backtester): {(realMedianTBB)} | {(btMedianTBB)}"
    )
    print(
        f"Average trades per day (Real | Backtester): {round(realtradesPerDay,4)} | {round(bttradesPerDay,4)}"
    )
    # print(f"Average time to trade (Real | Backtester): {(btAvgTradeTime)} | {(realAvgTradeTime)}")
    # print(f"Median time to trade (Real | Backtester): {(btMedianTradeTime)} | {(realMedianTradeTime)}")
    print("\n")
    print(
        f"Biggest loss (Real | Backtester): {realData['profit'].iloc[realbiggestLossIndex]} | {btData['profit'].iloc[btbiggestLossIndex]}"
    )
    print(
        f"Biggest win (Real | Backtester): {realData['profit'].iloc[realbiggestWinIndex]} | {btData['profit'].iloc[btbiggestWinIndex]}"
    )
    print(
        f"Tharp Expectancy (Real | Backtester): {round(realTharp, 4)} | {round(btTharp, 4)}"
    )
    # print(f"Biggest Loss (Real | Backtester): {realtradesPerDay} | {bttradesPerDay}")

    btPercProfit = (
        (btsellData["baseAmount"].iloc[-1] - btsellData["baseAmount"].iloc[0])
        / btsellData["baseAmount"].iloc[0]
        * 100
    )
    realPercProfit = (
        (realsellData["baseAmount"].iloc[-1] - realsellData["baseAmount"].iloc[0])
        / realsellData["baseAmount"].iloc[0]
        * 100
    )
    btValueProfit = btsellData["baseAmount"].iloc[-1] - btsellData["baseAmount"].iloc[0]
    realValueProfit = (
        realsellData["baseAmount"].iloc[-1] - realsellData["baseAmount"].iloc[0]
    )


    btAPM = ((((btPercProfit + 100) / 100) ** (1 / epochDurationDays)) ** 30 - 1) * 100
    realAPM = (
        (((realPercProfit + 100) / 100) ** (1 / epochDurationDays)) ** 30 - 1
    ) * 100

    print("\n")
    print(
        f"Total percent profit (Real | Backtester): {round(realPercProfit,3)}% | {round(btPercProfit,3)}%"
    )
    print(
        f"Total value profit (Real | Backtester): {round(realValueProfit,8)} | {round(btValueProfit,8)}"
    )
    print(
        f"Calculated APM (Real | Backtester): {round(btAPM,3)}% | {round(realAPM,3)}%"
    )


def monteCarlo(data, nSims, name="Test", maxSteps=None):
    data = data[data["buying"] == False]["profit"].dropna().tolist()
    if maxSteps is None:
        maxSteps = len(data)

    xList = [x for x in range(maxSteps + 1)]
    stepsList = []
    endResults = []
    maxdrawDownList = []

    fig, axs = plt.subplots(
        1,
        2,
        sharey=True,
        num=f"Monte Carlo {name}",
        gridspec_kw={"width_ratios": [3, 1]},
    )
    for _ in range(nSims):
        steps = [100]
        inDowntrend = True
        downTrendStart = 100
        simDrawDownList = []
        for u in range(maxSteps):
            result = ((random.choice(data) / 100) + 1) * steps[u]
            steps.append(result)
            if u == maxSteps - 1:
                endResults.append(result)
                simDrawDownList.append(steps[-1] - steps[-2])

            if inDowntrend:
                if steps[-2] < steps[-1]:
                    simDrawDownList.append(steps[-2] - downTrendStart)
                    inDowntrend = False
                if u == maxSteps - 1:
                    simDrawDownList.append(steps[-1] - downTrendStart)
                    inDowntrend = False

            if len(steps) > 2 and (steps[-2] > steps[-1] and steps[-3] < steps[-2]):
                inDowntrend = True
                downTrendStart = steps[-2]

        maxdrawDownList.append(min(simDrawDownList))

        axs[0].plot(xList, steps)
        stepsList.append(steps)

    maxGraphValue = max(endResults)
    minGraphValue = min(endResults)
    sampleMean = np.mean(endResults)
    sampleSTD = np.std(endResults)
    yNormDist = np.linspace(minGraphValue, maxGraphValue, 100)
    xNormDist = ss.norm.pdf(yNormDist, sampleMean, sampleSTD)
    thingy = np.linspace(0, np.max(xNormDist))
    probofLoss = round(ss.norm.cdf(100, sampleMean, sampleSTD) * 100, 4)
    medianProfit = np.median(endResults) - 100

    axs[1].plot(xNormDist, yNormDist)

    sigmaList = [
        sampleMean + 2 * sampleSTD,
        sampleMean + 1 * sampleSTD,
        sampleMean,
        sampleMean - 1 * sampleSTD,
        sampleMean - 2 * sampleSTD,
    ]

    for u in sigmaList:
        axs[1].plot(
            thingy, [u for x in thingy], linewidth=3, linestyle="--", color="orange"
        )
        axs[0].plot(
            xList, [u for x in xList], linewidth=3, linestyle="--", color="orange"
        )

    fig.suptitle(
        f"Monte Carlo {name} | simulations = {nSims} | steps = {maxSteps} | Prob. of Loss = {probofLoss}% | Median profit: = {round(medianProfit, 2)}%"
    )
    axs[0].set_xlabel(f"Steps / trades (-)")
    axs[1].set_xlabel(f"Probability (-)")
    axs[0].set_ylabel(f"Percentage of original (%)")
    axs[0].grid()
    axs[1].grid()

    medianMaxDrawDown = np.median(maxdrawDownList)
    medianReturn = np.median(endResults) - 100

    print(f"==== Monte Carlo Analysis for {name} ====")
    print(f"Probability of loss: {probofLoss}%")
    print(f"Median max drawdown: {round(medianMaxDrawDown,4)}%")
    print(f"Absolute Max drawdown: {round(max(maxdrawDownList),4)}%")
    print(f"Median return: {round(medianReturn,4)}%")
    print(f"Median Return/Drawdown: {round(-medianReturn/medianMaxDrawDown,4)}")
    print(f"=============================================")
    print("\n")

def plotBoughtInMatrix(coins, realData, btData):
    fig, axs = plt.subplots(1, 1, sharex=True, num=f"BoughtInMatrix")

    btsellData = btData[btData["buying"] == False]
    btbuyData = btData[btData["buying"] == True]
    realsellData = realData[realData["buying"] == False]
    realbuyData = realData[realData["buying"] == True]

    axs.plot(
        btbuyData["timestamp"],
        btbuyData["ticker"],
        marker="^",
        color="orange",
        linestyle="none",
        label="bt buy"
    )
    axs.plot(
        btsellData["timestamp"],
        btsellData["ticker"],
        marker="v",
        color="indigo",
        linestyle="none",
        label="bt sell"
    )
    axs.plot(
        realbuyData["timestamp"],
        realbuyData["ticker"],
        marker=".",
        color="lime",
        linestyle="none",
        label="real buy"
    )
    axs.plot(
        realsellData["timestamp"],
        realsellData["ticker"],
        marker=".",
        color="red",
        linestyle="none",
        label="real sell"
    )

    axs.grid()
    axs.legend()

if __name__ == "__main__":
    pass
    # redacted :)