"""
Handler for SPL token account close / burn services.
Program: F6fmDVCQfvnEq2KR8hhfZSEczfM9JK9fWbCsYJNbTGn7

These services burn unwanted tokens and close the associated SPL token account,
returning the rent-exemption SOL deposit to the wallet owner. The transaction has
two independent legs:

  1. SOL rent refund — return of own capital previously locked as rent when the token
     account was created. NOT a revenu, NOT a cession: it is the SAME SOL coming back.
     The rent paid AT CREATION already left the balance (swallowed in the buy Trade's
     SOL-out leg, e.g. handle_pumpfun), but was never emitted as a standalone Withdrawal.
     Recording the refund as a Deposit would assert "internal transfer in" with no
     matching Withdrawal -> a spurious POSITIVE transfers_mismatch (+~0.002 SOL), and a
     Deposit/_TRANSFER is the wrong claim (this SOL never came from another of my wallets).

     We instead emit it as GIFT_RECEIVED tagged `rent_refund`. Two reasons:
       - mechanically, GIFT_RECEIVED credits the SOL balance (correct) but does NOT touch
         the transfers_mismatch counter (audit.py only reacts to DEPOSIT/WITHDRAWAL) -> the
         spurious +0.002 disappears, balance stays exact;
       - fiscally (FR 150 VH bis), the refund is a NON-EVENEMENT NEUTRE: the SOL's cost is
         already in the cost basis (pta) from when it was first bought, so the pta must stay
         UNCHANGED. The FR module discriminates the `rent_refund` note tag -> maps to INTRA
         (pta unchanged), NOT ACQUIS_GRATUIT (which would re-add cost). Same note-tag
         discrimination mechanism as gambling_win / don_tiers / burn.
     See note below on keeping the network fee.

  2. The burned token itself — destroyed, not sold. A burn moves no token "transfer"
     (it is an spl-token `burn` instruction, not a transfer), so transfers_net never
     sees it and the token would otherwise keep a phantom residual balance forever.
     We emit an explicit outbound line per burned mint so the holding drops to zero.

Fiscal treatment of the burn (FR, 150 VH bis): a voluntary burn is NOT a cession à
titre onéreux (no price, no acquirer — the asset is annihilated), so it is neither a
taxable plus-value nor a deductible moins-value. It must NOT map to Spend/CASH_OUT
(which the FR module treats as a taxable cession). We emit it as a SPEND tagged with a
`burn ` comment prefix; the bittytax exporter promotes a burn-tagged SPEND to the
bittytax "Lost" type (non-disposal), which the FR module maps to a non-cession. Same
note-tag discrimination mechanism as gambling_win / don_tiers.

Note: we keep the network fee on the rent-refund row (unlike make_transfer_in_tx, which
wipes txinfo.fee) so that the SOL spent as fee is still decremented from the balance at
audit. Aligned with BOFiP BOI-RPPM-PVBMC-30-20 §50 (the fee is not a separate taxable
cession, it just reduces the holding).
"""
from staketaxcsv.common.make_tx import _make_tx_received, make_spend_tx, TX_TYPE_GIFT_RECEIVED
from staketaxcsv.sol.handle_simple import handle_unknown_detect_transfers
from staketaxcsv.sol.util_sol import amount_currency

# Comment prefix that the bittytax exporter recognises to promote a SPEND to "Lost"
# (token destroyed, not sold). Keep in sync with export_bittytax_csv().
BURN_COMMENT_PREFIX = "burn "

# Comment prefix that the FR tax module recognises to map the rent refund to INTRA
# (non-evenement neutre, pta unchanged) rather than ACQUIS_GRATUIT. The refund is emitted
# as GIFT_RECEIVED so it credits the balance without touching transfers_mismatch.
RENT_REFUND_COMMENT_PREFIX = "rent_refund "


def _burned_mints(txinfo):
    """Yield (raw_amount_string, mint) for every spl-token `burn` instruction in the tx,
    looking at both top-level and inner instructions."""
    for instruction in (txinfo.instructions or []):
        parsed = instruction.get("parsed") if isinstance(instruction, dict) else None
        if isinstance(parsed, dict) and parsed.get("type") == "burn":
            info = parsed.get("info", {})
            if info.get("amount") and info.get("mint"):
                yield info["amount"], info["mint"]
    for info in (txinfo.inner_parsed or {}).get("burn", []):
        if info.get("amount") and info.get("mint"):
            yield info["amount"], info["mint"]


def handle_token_close(exporter, txinfo):
    transfers_in, transfers_out, _ = txinfo.transfers_net

    # Leg 2: burned token(s) — emit one outbound line per mint so the holding hits zero.
    z_index = 0
    for raw_amount, mint in _burned_mints(txinfo):
        amount, currency = amount_currency(txinfo, raw_amount, mint)
        if amount and amount > 0:
            row = make_spend_tx(txinfo, amount, currency, z_index=z_index)
            # Empty the fee on the burn row: the network fee belongs to the rent-refund
            # leg below (or to handle_unknown_detect_transfers), never counted twice.
            row.fee = ""
            row.fee_currency = ""
            row.comment = BURN_COMMENT_PREFIX + (row.comment or "")
            exporter.ingest_row(row)
            z_index += 1

    # Leg 1: SOL rent refund from closing the SPL token account.
    # GIFT_RECEIVED (not TRANSFER): credits the SOL balance without adding a spurious
    # positive transfers_mismatch, and is tagged rent_refund so the FR module treats it
    # as a neutral capital return (INTRA, pta unchanged). See module docstring.
    if len(transfers_in) == 1 and len(transfers_out) == 0:
        received_amount, received_currency, _, _ = transfers_in[0]
        # _make_tx_received keeps txinfo.fee so the network fee still decrements the
        # SOL balance at audit.
        row = _make_tx_received(txinfo, received_amount, received_currency, TX_TYPE_GIFT_RECEIVED, z_index=z_index)
        row.comment = RENT_REFUND_COMMENT_PREFIX + "token_account_close " + (row.comment or "")
        exporter.ingest_row(row)
    elif z_index == 0:
        # No burn line emitted and not the simple rent-refund shape: fall back.
        handle_unknown_detect_transfers(exporter, txinfo)
