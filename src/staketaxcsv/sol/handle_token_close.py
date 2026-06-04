"""
Handler for SPL token account close / burn services.
Program: F6fmDVCQfvnEq2KR8hhfZSEczfM9JK9fWbCsYJNbTGn7

These services burn unwanted tokens and close the associated SPL token account,
returning the rent-exemption SOL deposit to the wallet owner.

Fiscal treatment: the SOL received is a return of own capital (previously locked
as rent when the token account was created).  Classified as Deposit (non-taxable).

Note: we keep the network fee on the row (unlike make_transfer_in_tx, which wipes
txinfo.fee) so that the SOL spent as fee is still decremented from the balance at
audit. Aligned with BOFiP BOI-RPPM-PVBMC-30-20 §50 (the fee is not a separate
taxable cession, it just reduces the holding).
"""
from staketaxcsv.common.make_tx import _make_tx_received, TX_TYPE_TRANSFER
from staketaxcsv.sol.handle_simple import handle_unknown_detect_transfers


def handle_token_close(exporter, txinfo):
    transfers_in, transfers_out, _ = txinfo.transfers_net

    # SOL rent refund from closing the SPL token account
    if len(transfers_in) == 1 and len(transfers_out) == 0:
        received_amount, received_currency, _, _ = transfers_in[0]
        # _make_tx_received (vs make_transfer_in_tx) keeps txinfo.fee so the
        # network fee still decrements the SOL balance at audit.
        row = _make_tx_received(txinfo, received_amount, received_currency, TX_TYPE_TRANSFER)
        row.comment = "token_account_close " + row.comment
        exporter.ingest_row(row)
    else:
        handle_unknown_detect_transfers(exporter, txinfo)
