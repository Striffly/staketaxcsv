"""
Handler for Pump.fun bonding curve transactions.
Program: 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P

Pump.fun buy  : SOL out → token in   → classified as TRADE
Pump.fun sell : token out → SOL in   → classified as TRADE

Small memecoin buys/sells (< FEE_THRESHOLD = 0.03 SOL) would otherwise have
their SOL leg swallowed by detect_fees() and collapse to a single _UNKNOWN leg.
We rebuild the swap from the raw transfers, netting out only the true gas
(see util_sol.swap_legs_from_raw).
"""
from staketaxcsv.common.make_tx import make_swap_tx
from staketaxcsv.sol.handle_simple import handle_unknown_detect_transfers
from staketaxcsv.sol.util_sol import swap_legs_from_raw


def handle_pumpfun(exporter, txinfo):
    transfers_in, transfers_out, _ = txinfo.transfers_net

    if len(transfers_in) == 1 and len(transfers_out) == 1:
        sent_amount, sent_currency, _, _ = transfers_out[0]
        received_amount, received_currency, _, _ = transfers_in[0]
        row = make_swap_tx(txinfo, sent_amount, sent_currency, received_amount, received_currency)
        exporter.ingest_row(row)
        return

    # transfers_net dropped the small SOL leg as "fee": rebuild the swap from raw.
    legs = swap_legs_from_raw(txinfo)
    if legs:
        sent_amount, sent_currency, received_amount, received_currency = legs
        row = make_swap_tx(txinfo, sent_amount, sent_currency, received_amount, received_currency)
        exporter.ingest_row(row)
        return

    handle_unknown_detect_transfers(exporter, txinfo)
