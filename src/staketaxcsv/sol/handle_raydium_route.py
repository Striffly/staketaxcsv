"""
Handler for Raydium AMM Routing transactions.
Program: routeUGWgWzqBWFcrCfv8tritsqukccJPu3q5GPP3xS

Routes swaps through multiple Raydium pools → always SOL ↔ token.
Classified as TRADE.
"""
from staketaxcsv.common.make_tx import make_swap_tx
from staketaxcsv.sol.handle_simple import handle_unknown_detect_transfers
from staketaxcsv.sol.util_sol import swap_legs_from_raw


def handle_raydium_route(exporter, txinfo):
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
