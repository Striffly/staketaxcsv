# OKX DEX aggregator: 6m2CDdhRgxpH4WjvdzxAYbGxwdGUz5MziiL5jek2kBma
#
# Routes swaps through underlying DEXs (Meteora, Raydium, ...) via a wrapped-SOL
# account it creates with `createAccountWithSeed`. That System instruction makes
# `is_simple_tx` classify the whole tx as `_STAKING_CREATE`, which only emits the
# gas fee and drops both swap legs. This handler must therefore run BEFORE the
# simple-tx branch in the dispatcher.
#
# Fiscalité FR : swap crypto<->crypto = sursis (Trade), re-neutralisé par le module FR.

from staketaxcsv.common.make_tx import make_swap_tx
from staketaxcsv.sol.handle_simple import handle_unknown_detect_transfers
from staketaxcsv.sol.util_sol import reset_fee_to_gas, swap_legs_from_raw


def handle_okx_dex(exporter, txinfo):
    txinfo.comment = "okx_dex"
    transfers_in, transfers_out, _ = txinfo.transfers_net

    if len(transfers_in) == 1 and len(transfers_out) == 1:
        received_amount, received_currency, _, _ = transfers_in[0]
        sent_amount, sent_currency, _, _ = transfers_out[0]
        row = make_swap_tx(txinfo, sent_amount, sent_currency, received_amount, received_currency)
        exporter.ingest_row(row)
        return

    # detect_fees may have swallowed a small SOL leg (< FEE_THRESHOLD): rebuild from raw.
    legs = swap_legs_from_raw(txinfo)
    if legs:
        sent_amount, sent_currency, received_amount, received_currency = legs
        reset_fee_to_gas(txinfo)  # the swallowed SOL leg is now in `sent`, not fee
        row = make_swap_tx(txinfo, sent_amount, sent_currency, received_amount, received_currency)
        exporter.ingest_row(row)
        return

    handle_unknown_detect_transfers(exporter, txinfo)
