"""
Handler for SPL token account close / burn services.
Program: F6fmDVCQfvnEq2KR8hhfZSEczfM9JK9fWbCsYJNbTGn7

These services burn unwanted tokens and close the associated SPL token account,
returning the rent-exemption SOL deposit to the wallet owner.

Fiscal treatment: the SOL received is a return of own capital (previously locked
as rent when the token account was created).  Classified as Deposit (non-taxable).
"""
from staketaxcsv.common.make_tx import make_transfer_in_tx
from staketaxcsv.sol.handle_simple import handle_unknown_detect_transfers


def handle_token_close(exporter, txinfo):
    transfers_in, transfers_out, _ = txinfo.transfers_net

    # SOL rent refund from closing the SPL token account
    if len(transfers_in) == 1 and len(transfers_out) == 0:
        received_amount, received_currency, _, _ = transfers_in[0]
        row = make_transfer_in_tx(txinfo, received_amount, received_currency)
        row.comment = "token_account_close " + row.comment
        exporter.ingest_row(row)
    else:
        handle_unknown_detect_transfers(exporter, txinfo)
