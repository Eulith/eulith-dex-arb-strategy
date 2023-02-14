# Overview
Simple script that will create a list of token pairs where the base pair is USDC. Then find prices for that token pair across DEXs. Then perform an arbitrage via an atomic transaction if the arbitrage is profitable after taking gas into consideration.

Once the program iterates through the full list of token pairs and DEXs, it will terminate.

This trade is not currently profitable because gas costs are far higher than the arbitrage profit (although the arb does exist).

# Instructions
1. Run `pip install -r requirements.txt`, the main library here is eulith-web3
2. Set wallet details in `config.py` (lines 26 & 27)
3. Copy/paste your refresh token in `config.py` on line 30
4. (optional) Set the network you wish to send transactions to, default is mainnet (line 29)
5. Fund your wallet with USDC
6. Run `python3 test_small_usdc_trades.py`; keep in mind web3.py needs python -v 3.9 or lower

