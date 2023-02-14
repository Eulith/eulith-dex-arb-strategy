from __future__ import print_function

import os.path

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
    
    print("Goodbye World - ending program...")

