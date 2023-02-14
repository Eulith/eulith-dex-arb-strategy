# Overview
Simple script that will create a list of token pairs where the base pair is USDC. Then find prices for that token pair across DEXs. Then perform an arbitrage via an atomic transaction if the arbitrage is profitable after taking gas into consideration.

Once the program iterates through the full list of token pairs and DEXs, it will terminate.

This trade is not currently profitable because gas costs are far higher than the arbitrage profit (although the arb does exist).

Importantly, this program will lose money when it tries to execute an arb where the total gas required is higher than the gas limit.

# Instructions
1. Run `pip install -r requirements.txt`, the main library here is eulith-web3
2. Set wallet details in `config.py` (lines 26 & 27)
3. Copy/paste your refresh token in `config.py` on line 30
4. (optional) Set the network you wish to send transactions to, default is mainnet (line 29)
5. Fund your wallet with USDC
6. Run `python3 test_small_usdc_trades.py`; keep in mind web3.py needs python -v 3.9 or lower

# Your Next Steps
We're providing you with the infrastructure and some foundation code to run your own strategies. Because we do not trade ourselves (it would be a conflict of interest), we haven't done the reserach and improvements required to make this code profitable - that is your job. 

Here are the areas of improvement we'd suggest looking at first:
1) Dynamic gas pricing (or price predictions) - price gas accurately for each trade to balance getting executed and making a profit
2) Better handling of gas usage limits - right now it's determined by the aggregator (see get_gas_usage_given_aggregator() in master_trading_code. A better way to do it would be to simulate paths and then cache the gas used to asynchronously update per block.
3) Run on other networks (we support all EVM networks), for other token pairs (we support all ERC20 and ERC721 tokens on all EVM networks), it takes us 1 day to add another token standard, and for other DEXs
4) Add "flash swap" with `ew3.v0.start_uni_swap` or flash loan with `ew3.v0.start_flash_loan`
5) Use your own DEX integrations instead of the aggregagor to optimize gas and avoid (or reduce) swap path variance
6) There's lots more you can do with the product, but that's where we'd look at first around improving this code / trade


# Eulith TODO:

This is for us to do with this code, so you know what's coming.

* Fix gas estimation code
* Add Google sheet logging option/file for ease of use
* Clean up code
* Add testing harness
* .gitignore additions
* Add better documentation & comments to master_trading_code
* Keep funds in wallet instead of toolkit
