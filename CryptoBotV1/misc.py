from datetime import datetime
import pandas as pd
import os
import pandas_ta as ta
from tqdm import tqdm as tqdm
import glob
import logging

log = logging.getLogger("bot")


def getLatestDataV2(priceWS, dat: dict, timeFrame: str, coins: list, base: str = "BTC"):
    """Get the last row of historical data

    Args:
        dat (dict): datadict in default format
        timeFrame (str): the time format to look at

    Returns:
        (bool, dict): callback if price retrieved, updated datadict with latest data
    """
    dataSets = list(dat.keys())
    # update = getHistWSv2(coins, timeFrame, base)
    while True:
        if priceWS.updated[timeFrame]:
            update = priceWS.histData
            priceWS.updated[timeFrame] = False
            break

    for dataSet in dataSets:
        idd = dataSet.split("_")
        iddTicker = idd[0]
        iddTimeFrame = idd[1]
        if iddTimeFrame == timeFrame:
            currentDf = dat[dataSet]
            temp = update[f"{iddTicker}_{iddTimeFrame}"]
            # delete oldest
            currentDf = currentDf.iloc[1:]
            # add latest
            currentDf = pd.concat([currentDf, temp])

            if currentDf.index[-1] == currentDf.index[-2]:
                log.warning("duplication error")
            else:
                dat[dataSet] = currentDf

    return dat


def getLastTradeData(foldername="logData"):
    list_of_files = glob.glob(os.path.join(f"{foldername}/*0.csv"))
    latest_file = max(list_of_files, key=os.path.getctime)

    P = pd.read_csv(latest_file)
    P = P[P["failed"].isin([False, "False"])]
    P["timestamp"] = pd.to_datetime(P["timestamp"])
    P = P.iloc[-3:, 1::]

    assert len(P) >= 3, f"Latest trade data fail\n {P}"

    return P


def awaitStart():
    log.debug(f"Awaiting start...")
    while True:
        if (int(datetime.now().strftime("%S")) > 0) and (
            int(datetime.now().strftime("%S")) < 4
        ):
            break
        else:
            continue
    log.debug(f"Starting...")


def storeMiscData(websocket, base="BTC", file="logData/miscData.csv"):
    if not os.path.exists(file):
        file = open(file, "a+")
        file.write("date,BNBPrice,baseName,basePrice\n")
        file.write(
            f"{datetime.now()},{websocket.BNBPrice},{base},{websocket.basePrice}\n"
        )
    else:
        file = open(file, "a")
        file.write(
            f"{datetime.now()},{websocket.BNBPrice},{base},{websocket.basePrice}\n"
        )

    file.close()


def logTradeData(tradeData, startTime, fail=False, foldername="logData"):
    """Saves tradeData to csv file.

    Args:
        tradeData (pandas.Dataframe): tradeData dataframe
        startTime (str): time that run started as a save key
        foldername (str, optional): folder name. Defaults to "logData".
    """
    if fail:
        if not os.path.exists(foldername):
            os.mkdir(os.path.join(foldername + fail))
        filename = (f"{foldername}/{startTime}.csv").replace(":", "").replace(" ", "")
        tradeData.to_csv(filename)
        log.info("Trade failed!")
    else:
        if not os.path.exists(foldername):
            os.mkdir(os.path.join(foldername))
        filename = (f"{foldername}/{startTime}.csv").replace(":", "").replace(" ", "")
        tradeData.to_csv(filename)
        log.info(f"New trade!")
        log.info(f"\n{(tradeData.iloc[-1]).to_frame().T}\n")


class RetrievalFail(Exception):
    pass


class LockedError(Exception):
    pass


class TradeFail(Exception):
    pass


def storeSaveData(time, baseAmount, lastBuyPrice, filename="storedData/storedData.csv"):
    data = {"time": time, "baseAmount":baseAmount, "lastBuyPrice": lastBuyPrice}
    P = pd.Series(data)
    P.to_csv(filename)

def loadSaveData(filename="storedData/storedData.csv"):
    P = pd.read_csv(filename, index_col=0).squeeze("columns")
    time, baseAmount, lastBuyPrice = P["time"], P["baseAmount"], P["lastBuyPrice"]
    time = pd.to_datetime(time)
    return time, float(baseAmount), float(lastBuyPrice)


def saveMarketData(dat, coins, base, folder="marketData"):
    for coin in coins:
        dat[f"{coin}{base}_1m"].to_csv(f"{folder}/{coin}{base}_1m.csv")