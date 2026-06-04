# Swap V2 Program: SwaPpA9LAaLfeLi3a68M4DjnLqgtticKg6CnyNwgAC8

from staketaxcsv.common.make_tx import make_swap_tx
from staketaxcsv.sol.constants import LOG_INSTRUCTION_SWAP
from staketaxcsv.sol.handle_simple import handle_unknown
from staketaxcsv.sol.util_sol import reset_fee_to_gas, swap_legs_from_raw


def handle_program_swap_v2(exporter, txinfo):
    log_instructions = txinfo.log_instructions

    if LOG_INSTRUCTION_SWAP in log_instructions:
        _handle_swap(exporter, txinfo)
    else:
        handle_unknown(exporter, txinfo)


def _handle_swap(exporter, txinfo):
    _transfers_in, _transfers_out, transfers_unknown = txinfo.transfers_net

    transfers_in = _transfers_in[:]
    transfers_out = _transfers_out[:]

    # Remove small fees
    if len(transfers_out) == 2:
        for i, transfer_out in enumerate(transfers_out):
            sent_amount, sent_currency, _, _ = transfer_out
            if sent_amount < .0001:
                transfers_out.pop(i)
    if len(transfers_in) == 2:
        for i, transfer_in in enumerate(transfers_in):
            received_amount, received_currency, _, _ = transfer_in
            if received_amount < .0001:
                transfers_in.pop(i)

    if len(transfers_in) == 1 and len(transfers_out) == 1:
        sent_amount, sent_currency, _, _ = transfers_out[0]
        received_amount, received_currency, _, _ = transfers_in[0]

        row = make_swap_tx(txinfo, sent_amount, sent_currency, received_amount, received_currency)
        exporter.ingest_row(row)
    else:
        # detect_fees may have swallowed a small SOL leg (< FEE_THRESHOLD): rebuild from raw.
        legs = swap_legs_from_raw(txinfo)
        if legs:
            sent_amount, sent_currency, received_amount, received_currency = legs
            reset_fee_to_gas(txinfo)  # the swallowed SOL leg is now in `sent`, not fee
            row = make_swap_tx(txinfo, sent_amount, sent_currency, received_amount, received_currency)
            exporter.ingest_row(row)
        else:
            handle_unknown(exporter, txinfo)
