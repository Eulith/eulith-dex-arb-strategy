from __future__ import print_function

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import datetime

import boto3
from eulith_web3.kms import KmsSigner

from eulith_web3.eulith_web3 import *
from eulith_web3.signing import construct_signing_middleware

import config

# --- GLOBAL VARIABLES ---
ew3 = config.ew3
wallet = config.wallet
network_url = config.network_url

weth = ew3.eulith_get_erc_token(TokenSymbol.WETH)
usdt = ew3.eulith_get_erc_token(TokenSymbol.USDT)
usdc = ew3.eulith_get_erc_token(TokenSymbol.USDC)
link = ew3.eulith_get_erc_token(TokenSymbol.LINK)
matic = ew3.eulith_get_erc_token(TokenSymbol.MATIC)
bnb = ew3.eulith_get_erc_token(TokenSymbol.BNB)
busd = ew3.eulith_get_erc_token(TokenSymbol.BUSD)
steth = ew3.eulith_get_erc_token(TokenSymbol.STETH)
matic = ew3.eulith_get_erc_token(TokenSymbol.MATIC)   
ldo = ew3.eulith_get_erc_token(TokenSymbol.LDO)
crv = ew3.eulith_get_erc_token(TokenSymbol.CRV)
cvx = ew3.eulith_get_erc_token(TokenSymbol.CVX)
badger = ew3.eulith_get_erc_token(TokenSymbol.BADGER)
bal = ew3.eulith_get_erc_token(TokenSymbol.BAL)    
oneinch = ew3.eulith_get_erc_token(TokenSymbol.ONEINCH)
uni = ew3.eulith_get_erc_token(TokenSymbol.UNI)
ape = ew3.eulith_get_erc_token(TokenSymbol.APE)
gmt = ew3.eulith_get_erc_token(TokenSymbol.GMT)

#------------------------

def write_trade_to_gsheet(receipt, spread_in_sell_token_units: float,
                            min_dex, max_dex, sell_token, buy_token, gas_cost_in_sell_token):
    sheet = config.SHEET

    value_range_body = {
    "majorDimension": "ROWS",
    "range": "Trade History!B:L",
    "values": [
        [str(datetime.datetime.now()), str(receipt), 
        str(receipt["transactionHash"].hex()),
        spread_in_sell_token_units, str(receipt["gasUsed"]), 
        str(receipt["effectiveGasPrice"]),
        gas_cost_in_sell_token,
        sell_token.address, buy_token.address,
        str(min_dex['dex']).split(".")[1], 
        str(max_dex['dex']).split(".")[1], 
        network_url]
        ]
    }

    req = sheet.values().append(spreadsheetId=config.SAMPLE_SPREADSHEET_ID,
                            range=config.SAMPLE_RANGE_NAME,
                            valueInputOption='RAW',
                            insertDataOption='INSERT_ROWS',
                            body=value_range_body)
    res = req.execute()
    return res

def print_trade_summary(SELL_AMOUNT: int, SELL_TOKEN, buy_leg,
                        spread_in_sell_token_units, 
                        gas_cost_in_sell_token):
    print('\n~~~~~~~~~~~~~TRADE SUMMARY~~~~~~~~~~~~~~~~~')
    print(f"Started with: {SELL_AMOUNT} of {SELL_TOKEN.address}")
    print(f"Ending with: {buy_leg} of {SELL_TOKEN.address}")
    print(f"Profit: {spread_in_sell_token_units} sell tokens")
    print(f"Gas cost (sell token): {gas_cost_in_sell_token}")

def fund_toolkit_contract_if_needed(proxy_amount: float, proxy_token, 
                                    proxy_token_decimals: int):
    '''
    proxy_token's type is Union[EulithERC20, EulithWETH]
    '''
    # create toolkit contract if it doesn't exist already
    ew3.eulith_create_contract_if_not_exist(wallet.address)

    # --- Fund Proxy Contract IF Insufficient Sell Token ---- #
    proxy_contract_address = ew3.eulith_contract_address(wallet.address)
    print("Proxy contract address is: {}".format(proxy_contract_address))
    sell_token_proxy_balance = proxy_token.balance_of(proxy_contract_address)
    # print(f"Sell token proxy balance is: {sell_token_proxy_balance}")
    sell_token_proxy_balance = sell_token_proxy_balance / proxy_token_decimals

    print("Proxy balance is {}".format(sell_token_proxy_balance))

    if sell_token_proxy_balance < proxy_amount:
        print(f"Funding toolkit contract...")
        if proxy_token.address == "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2":  # WETH address
            print("Sell token address is WETH, converting ETH to WETH")
            # convert eth to weth to prepare for the swap
            # eth_to_weth_tx = weth.deposit_eth(proxy_amount)
            eth_to_weth_tx = weth.deposit_wei(int(proxy_amount*proxy_token_decimals))
            eth_to_weth_tx['from'] = wallet.address

            # print(f"Proxy amount is: {proxy_amount}")

            rec = ew3.eth.send_transaction(eth_to_weth_tx)
            receipt = ew3.eth.wait_for_transaction_receipt(rec)

        amount_to_send_in_sell_token = proxy_amount - sell_token_proxy_balance
        print("Funding Proxy with {} in token type {}".format(amount_to_send_in_sell_token, proxy_token.address))

        tx = proxy_token.transfer(proxy_contract_address, int(amount_to_send_in_sell_token * proxy_token_decimals), 
                                override_tx_parameters = {'from': wallet.address})
        rec = ew3.eth.send_transaction(tx)
        receipt = ew3.eth.wait_for_transaction_receipt(rec)

        print(f"Funding Proxy hash: {receipt['transactionHash'].hex()}")

    else:
        print("Proxy balance does not need funding.")
    # --------------------------- #

def create_list_of_token_pair_tuples(base_token, tokens):
    '''
    Here I am using nested for loops to get the grid of all possible tuple combinations of the token objects from tokens, 
    which is 136 combinations. here are 17 coins, can't pair with itself so 16 coins it can pair with, 
    resulting in pairing a with b then b with a, so dividing by 2 to eliminate duplicates. aka 17 choose 2
    '''
    if tokens == None:
        tokens = get_list_of_all_tokens()
    
    pairs=[]

    if base_token:
        print(f"Creating list of tuples with base token: {base_token.address}")
        for i in range(len(tokens)):         
            pairs.append((base_token, tokens[i]))

    else:
        print(f"Creating list of tuples without base token representing all possible combinations")
        for i in range(len(tokens)):         
            for j in range(i+1, len(tokens)):
                pairs.append((tokens[i], tokens[j]))

    return pairs

def create_list_of_only_usdc_pair_tuples():
    '''
    Creating a list of pairs (as tuples), where the first element in tuple is USDC and the second is another token
    All tokens defined as global variables should be in the tokens list (except usdc)
    '''
    return create_list_of_token_pair_tuples(usdc, None)

def create_short_list_of_token_pair_tuples():
    tokens = [weth, usdt, usdc]
    return create_list_of_token_pair_tuples(None, token)

def get_list_of_all_dexs():
    dexs = [EulithLiquiditySource.UNISWAP_V3, 
            EulithLiquiditySource.BALANCER_V2,
            EulithLiquiditySource.SUSHI,
            EulithLiquiditySource.COMPOUND,
            EulithLiquiditySource.PANCAKE,
            EulithLiquiditySource.CURVE_V2,
            EulithLiquiditySource.CURVE_V1,
            EulithLiquiditySource.SADDLE,
            EulithLiquiditySource.SYNAPSE,
            EulithLiquiditySource.BALANCER_V1]

    return dexs

def get_list_of_all_tokens():
    # these are python bindings around the whole ERC20 contract
    # removed link because too gas expensive
    # TODO: add link back when gas logic is more dynamic
    tokens = [weth, usdt, usdc, matic, bnb, busd, steth, ldo, crv, cvx, badger, bal, oneinch, uni, ape, gmt]
    return tokens

def get_min_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs, aggregator = None):
    price_per_dex = ()
    min_dex = {"dex": 0, "price": 2e16, "txs":[]}

    for dex in dexs:
        print(f'Requesting buy leg quote from: {dex}')
        # set the swap parameters
        swap_params = -1

        if aggregator == None:
            swap_params = EulithSwapRequest(
                sell_token=SELL_TOKEN,
                buy_token=BUY_TOKEN,
                sell_amount=SELL_AMOUNT,
                liquidity_source=dex,
                recipient=ew3.eulith_contract_address(wallet.address),
                slippage_tolerance=0
                )
        else:
            swap_params = EulithSwapRequest(
            sell_token=SELL_TOKEN,
            buy_token=BUY_TOKEN,
            sell_amount=SELL_AMOUNT,
            liquidity_source=dex,
            recipient=ew3.eulith_contract_address(wallet.address),
            slippage_tolerance=0,
            route_through=aggregator)

        try:
            # this is just to make it easy to read later
            # get a swap quote
            # txs is an array of transactions that make up the swap
            buy_leg_price, buy_leg_txs = ew3.eulith_swap_quote(swap_params)

            # get the min price and associated DEX
            if (buy_leg_price != None) and buy_leg_price < min_dex["price"]:
                min_dex["dex"] = dex
                min_dex["price"] = buy_leg_price
                min_dex["txs"] = buy_leg_txs

        except EulithRpcException:
            continue
    
    return min_dex

def get_max_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs, aggregator = None):
    max_dex_price = 1e10
    max_dex_txs = []
    max_dex = {"dex": 0, "price": 2e16, "txs":[]}
    for dex in dexs:
        print(f'Requesting sell leg quote from: {dex}')
        swap_params = -1
        
        # buy token and sell token reversed from get_min TODO: make more intuitive
        if aggregator == None:
            swap_params = EulithSwapRequest(
                    sell_token=BUY_TOKEN,
                    buy_token=SELL_TOKEN,
                    sell_amount=SELL_AMOUNT,
                    liquidity_source=dex,
                    slippage_tolerance=0
                    )
        else:
            swap_params = EulithSwapRequest(
                    sell_token=BUY_TOKEN,
                    buy_token=SELL_TOKEN,
                    sell_amount=SELL_AMOUNT,
                    liquidity_source=dex,
                    slippage_tolerance=0,
                    route_through=aggregator) 

        try:
            sell_leg_price, sell_leg_txs = ew3.eulith_swap_quote(swap_params)
            if sell_leg_price < max_dex["price"]:
                max_dex["dex"] = dex
                max_dex["price"] = sell_leg_price
                max_dex["txs"] = sell_leg_txs

        except EulithRpcException:
            continue

    return max_dex

def get_gas_usage_given_aggregator(aggregator):
    gas_usage = -1 # initiate variable to check later, reject txn if wrong
    if aggregator == EulithSwapProvider.ZERO_EX:
        gas_usage = 800000
    elif aggregator == EulithSwapProvider.ONE_INCH:
        gas_usage = 450000
    else:
        print("!! Gas calculation ERROR. !!")
        exit(1)

    return gas_usage

def get_gas_cost_in_sell_token(aggregator, max_gas_price, SELL_TOKEN, BUY_TOKEN):
    gas_usage = get_gas_usage_given_aggregator(aggregator)
    max_gas_price = max_gas_price / 1e18 # do this first to avoid multiplying large numbers
    gas_cost_in_eth = max_gas_price * gas_usage
    max_gas_price = max_gas_price * 1e18

    if SELL_TOKEN.address != "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2":
        # need to get a price for eth and the sell token, to calculate gas in sell token
        swap_params = EulithSwapRequest(
            sell_token=SELL_TOKEN,
            buy_token=BUY_TOKEN,
            sell_amount=1.0 # value doesn't matter here
            )

        try:
            sell_token_to_eth_price, txs = ew3.eulith_swap_quote(swap_params)

        except EulithRpcException:
            # TODO: need to handle exception better without stopping loop
            sell_token_to_eth_price = 1e18

        gas_cost_in_sell_token = gas_cost_in_eth * sell_token_to_eth_price

    else:  # if it is eth, then skip the pricing, etc.
        gas_cost_in_sell_token = gas_cost_in_eth

    return gas_cost_in_sell_token


if __name__ == '__main__':
    print("Hello World - starting program...")
    wallet = config.wallet
    print(f"Wallet address is {wallet.address}")

    # deploy the Eulith proxy contract
    ew3.eulith_create_contract_if_not_exist(wallet.address)

    pairs = create_list_of_only_usdc_pair_tuples()

    # a list of profitable trades, where each element is an list of unsigned txns
    
    while True:
        max_pair = None
        counter = 0
        max_profitability = -1

        SELL_AMOUNT = 1
        SELL_TOKEN_DECIMALS = 1e6

        # --------------- KEY PARAMETERS ------------------------ #
        # SELL_TOKEN is referring to the first element in each tuple from pairs, a list of tuples(sell_token,buy_token)
        SELL_TOKEN = pairs[counter][0]
        # BUY_TOKEN is referring to the second element in each tuple from pairs, a list of tuples(sell_token,buy_token)
        BUY_TOKEN = pairs[counter][1]
        # ------------------------------------------------------- #
        
        fund_toolkit_contract_if_needed(SELL_AMOUNT, SELL_TOKEN, SELL_TOKEN_DECIMALS)

        dexs = get_list_of_all_dexs()
        aggregator = EulithSwapProvider.ZERO_EX

        min_dex = get_min_dex(SELL_TOKEN, BUY_TOKEN, SELL_AMOUNT, dexs, aggregator)
        if min_dex == None: 
            print("Error getting min_dex. LOC 385")
            exit(1)

        # now let's do the trade, we're going to buy on the min dex
        ew3.eulith_start_transaction(wallet.address)
        # construct atomic unit
        ew3.eulith_send_multi_transaction(min_dex["txs"])

        sell_amount_of_buy_token = round(SELL_AMOUNT / min_dex["price"], 2)

        max_dex = get_max_dex(SELL_TOKEN, BUY_TOKEN, sell_amount_of_buy_token, dexs, aggregator)
        if max_dex == None: 
            print("Error getting min_dex. LOC 398")
            exit(1)

        # check condition
        buy_leg = sell_amount_of_buy_token / max_dex["price"]    # the amount of sell_token resulting from buy_token sell
        spread_in_sell_token_units = (buy_leg - SELL_AMOUNT)  # positive if profitable

        # !! Setting gas cost parameters as a constants for now, should improve later !!
        gas_max_priority_fee = 5000000000 # 5 Gwei, minner tip (in addition to base price)
        max_gas_price = 35000000000 # 35 Gwei

        gas_cost_in_sell_token = get_gas_cost_in_sell_token(aggregator, max_gas_price, SELL_TOKEN, BUY_TOKEN)

        print_trade_summary(SELL_AMOUNT, SELL_TOKEN, buy_leg,
                            spread_in_sell_token_units, 
                            gas_cost_in_sell_token)

        # Defining where the profit comes from, and saving the maximum profit for the max_pair every time a new 
        profitability = spread_in_sell_token_units - gas_cost_in_sell_token

        if profitability > max_profitability:
            max_profitability = profitability
            max_pair = pairs[counter]

        if spread_in_sell_token_units > gas_cost_in_sell_token:
            ew3.eulith_send_multi_transaction(max_dex["txs"])
            # finish building the transaction
            atomic_tx = ew3.eulith_commit_transaction()

            # setting the gas limit
            atomic_tx['maxFeePerGas'] = int(max_gas_price)
            atomic_tx['maxPriorityFeePerGas'] = gas_max_priority_fee
            atomic_tx['gas'] = get_gas_usage_given_aggregator(aggregator)

            print("I would send, but don't want to this time")
            exit(1)
            # send the transaction!
            # tx = ew3.eth.send_transaction(atomic_tx)
            # receipt = ew3.eth.wait_for_transaction_receipt(tx)
            print(f"!! TRANSACTION EXECUTED !!\n\n{receipt}")
               
            write_trade_to_gsheet(receipt)

        else:
            print("Transaction not executed, profit < loss")
        
            print(f"The sell_token right now is:",pairs[counter][0])
            print(f"The buy_token right now is:",pairs[counter][1])
            print("Waiting for next block.....")
            print(f"The max profit is:", max_profitability)
            print(f"The max pair is:", max_pair)#max pair is the single tuple of the token pair that will produce the most profit, which we set SELL_TOKEN and BUY_TOKEN to instead of hardcoding them 
            counter += 1
            print(f"The pair I am currently checking is:", counter)

            if counter >= len(pairs):
                exit(1)
                print(f"Finished all pairs.")













    exit(1)
# ----------------- #


    if token == len(tokens) - 1:
        # SUBMITTING MAX PROFIT TRANSACTION
        # Every iteration over the 136 pair combinations in our pairs list, submit one transaction, the max profit one named max_pair
        # --------------- KEY PARAMETERS ------------------------ #
        SELL_AMOUNT = 100000
        SELL_TOKEN = max_pair[0]# this is the 1st element in the max pair tuple
        SELL_TOKEN_DECIMALS = 1e6
        BUY_TOKEN = max_pair[1]# this is the 2nd element in the max pair tuple
        # ------------------------------------------------------- #

        dexs = [EulithLiquiditySource.UNISWAP_V3, 
                EulithLiquiditySource.BALANCER_V2,
                EulithLiquiditySource.SUSHI,
                EulithLiquiditySource.COMPOUND,
                EulithLiquiditySource.PANCAKE,
                EulithLiquiditySource.CURVE_V2,
                EulithLiquiditySource.CURVE_V1,
                EulithLiquiditySource.SADDLE,
                EulithLiquiditySource.SYNAPSE,
                EulithLiquiditySource.BALANCER_V1]

        price_per_dex = ()
        # (dex, price, txs)
        min_dex = (0, 2e16, [])

        aggregator = EulithSwapProvider.ZERO_EX
        # --- Fund Proxy Contract IF Insufficient Sell Token ---- #
        proxy_contract_address = ew3.eulith_contract_address(wallet.address)
        print("Proxy contract address is: {}".format(proxy_contract_address))
        sell_token_proxy_balance = SELL_TOKEN.balance_of(proxy_contract_address)
        sell_token_proxy_balance = sell_token_proxy_balance / SELL_TOKEN_DECIMALS

        print("Proxy balance is {}".format(sell_token_proxy_balance))

        if sell_token_proxy_balance < SELL_AMOUNT:
            if SELL_TOKEN.address == "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2":  # WETH address
                print("Sell token address is WETH, converting ETH to WETH")
                # convert eth to weth to prepare for the swap
                eth_to_weth_tx = weth.deposit_eth(SELL_AMOUNT)
                eth_to_weth_tx['from'] = wallet.address
                ew3.eth.send_transaction(eth_to_weth_tx)

            # # send to proxy
            # print("Funding Proxy with {} in {}".format(SELL_AMOUNT, SELL_TOKEN.address))
            # tx = SELL_TOKEN.transfer(proxy_contract_address, int(SELL_AMOUNT * SELL_TOKEN_DECIMALS))
            # tx['from'] = wallet.address
            # ew3.eth.send_transaction(tx)

        else:
            print("Proxy balance does not need funding.")
        # --------------------------- #

        for dex in dexs:
            print(f'Requesting buy leg quote from: {dex}')
            # set the swap parameters
            swap_params = EulithSwapRequest(
                sell_token=SELL_TOKEN,
                buy_token=BUY_TOKEN,
                sell_amount=SELL_AMOUNT,
                liquidity_source=dex,
                recipient=ew3.eulith_contract_address(wallet.address),
                route_through=aggregator)

            try:
                # this is just to make it easy to read later
                # get a swap quote
                # txs is an array of transactions that make up the swap
                price, txs = ew3.eulith_swap_quote(swap_params)

                # get the min price and associated DEX
                if (price != None) and price < min_dex[1]:
                    min_dex = (dex, price, txs)
            except EulithRpcException:
                continue

        # now let's do the trade
        # we're going to buy on the dex with the lowest price and sell the dex with the highest
        # we're going to do this trade atomically, so both legs will succeed or both will fail
        ew3.eulith_start_transaction(wallet.address)

        # construct atomic unit
        ew3.eulith_send_multi_transaction(min_dex[2])

        # construct the sell leg by switching the buy_token and sell_token in the quote request
        sell_amount_of_buy_token = round(SELL_AMOUNT / min_dex[1], 2)
        max_dex_price = 1e10
        max_dex_txs = []
        max_dex = None
        for dex in dexs:
            print(f'Requesting sell leg quote from: {dex}')
            swap_params = EulithSwapRequest(
                    sell_token=BUY_TOKEN,
                    buy_token=SELL_TOKEN,
                    sell_amount=sell_amount_of_buy_token,
                    liquidity_source=dex,
                    route_through=aggregator)

            try:
                sell_leg_price, sell_leg_txs = ew3.eulith_swap_quote(swap_params)
                if sell_leg_price < max_dex_price:
                    max_dex_price = sell_leg_price
                    max_dex_txs = sell_leg_txs
                    max_dex = dex
            except EulithRpcException:
                continue

        # check condition
        buy_leg = sell_amount_of_buy_token / max_dex_price    # the amount of sell_token resulting from buy_token sell
        spread_in_sell_token_units = (buy_leg - SELL_AMOUNT)  # positive if profitable

        # !! Setting gas cost parameters as a constants for now, should improve later !!
        gas_max_priority_fee = 5000000000 # 5 Gwei, minner tip (in addition to base price)
        max_gas_price = 35000000000 # 35 Gwei
        gas_usage = 0

        if aggregator == EulithSwapProvider.ZERO_EX:
            gas_usage = 800000
        elif aggregator == EulithSwapProvider.ONE_INCH:
            gas_usage = 360000
        else:
            print("!! Gas calculation ERROR. !!")
            exit(1)

        max_gas_price = max_gas_price / 1e18 # do this first to avoid multiplying large numbers
        gas_cost_in_eth = max_gas_price * gas_usage
        max_gas_price = max_gas_price * 1e18

        if SELL_TOKEN.address != "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2":
            # need to get a price for eth and the sell token, to calculate gas in sell token
            swap_params = EulithSwapRequest(
                sell_token=SELL_TOKEN,
                buy_token=weth,
                sell_amount=1.0)

            sell_token_to_eth_price, txs = ew3.eulith_swap_quote(swap_params)
            gas_cost_in_sell_token = gas_cost_in_eth * sell_token_to_eth_price
        else:  # if it is eth, then skip the pricing, etc.
            gas_cost_in_sell_token = gas_cost_in_eth

        print()
        print('~~~~~~~~~~~~~TRADE SUMMARY~~~~~~~~~~~~~~~~~')
        print(f"Started with: {SELL_AMOUNT} {SELL_TOKEN.address}")
        print(f"Ending with: {buy_leg} {SELL_TOKEN.address}")
        print(f"Profit: {spread_in_sell_token_units} sell tokens")
        print(f"Gas cost (ETH): {gas_cost_in_eth}")
        print(f"Gas cost (sell token): {gas_cost_in_sell_token}")

        # # Defining where the profit comes from, and saving the maximum profit for the max_pair every time a new 
        # profitability  = spread_in_sell_token_units - gas_cost_in_sell_token +1000000
        # if profitability > max_profitability:
        #     max_profitability = profitability
        #     max_pair = pairs[counter]

        if spread_in_sell_token_units > gas_cost_in_sell_token:
            ew3.eulith_send_multi_transaction(max_dex_txs)
            # finish building the transaction
            atomic_tx = ew3.eulith_commit_transaction()

            # setting the gas limit
            atomic_tx['maxFeePerGas'] = int(max_gas_price)
            atomic_tx['maxPriorityFeePerGas'] = gas_max_priority_fee
            atomic_tx['gas'] = gas_usage

            print("I would send, but don't want to this time")
            exit(1)
            # send the transaction!
            # tx = ew3.eth.send_transaction(atomic_tx)
            # receipt = ew3.eth.wait_for_transaction_receipt(tx)
            # print("!! TRANSACTION EXECUTED !!")
            # print(receipt)
                    
            
            value_range_body = {
                "majorDimension": "ROWS",
                "range": "Trade History!B:L",
                "values": [
                    [str(datetime.datetime.now()), str(receipt), str(receipt["transactionHash"].hex()),
                    spread_in_sell_token_units, str(receipt["gasUsed"]), str(receipt["effectiveGasPrice"]),
                    "USDC", "WETH", str(min_dex[0]).split(".")[1], str(max_dex).split(".")[1], network_url]
                ] 
            }

            req = sheet.values().append(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                                        range=SAMPLE_RANGE_NAME,
                                        valueInputOption='RAW',
                                        insertDataOption='INSERT_ROWS',
                                        body=value_range_body)
            res = req.execute()


        else:
            print("Transaction not executed, profit < loss")
        print("Exited")

        print("Goodbye World - ending program...")

