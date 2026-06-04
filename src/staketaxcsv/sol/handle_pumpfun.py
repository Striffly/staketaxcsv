"""
Handler for Pump.fun bonding curve transactions.
Program: 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P

Pump.fun buy  : SOL out → token in   → classified as TRADE
Pump.fun sell : token out → SOL in   → classified as TRADE
"""
from staketaxcsv.common.make_tx import make_swap_tx
from staketaxcsv.sol.handle_simple import handle_unknown_detect_transfers


def handle_pumpfun(exporter, txinfo):
    transfers_in, transfers_out, _ = txinfo.transfers_net

    if len(transfers_in) == 1 and len(transfers_out) == 1:
        sent_amount, sent_currency, _, _ = transfers_out[0]
        received_amount, received_currency, _, _ = transfers_in[0]
        row = make_swap_tx(txinfo, sent_amount, sent_currency, received_amount, received_currency)
        exporter.ingest_row(row)
    else:
        handle_unknown_detect_transfers(exporter, txinfo)
