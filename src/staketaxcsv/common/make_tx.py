from staketaxcsv.common.Exporter import Row
from staketaxcsv.common.ExporterTypes import (
    TX_TYPE_AIRDROP,
    TX_TYPE_BORROW,
    TX_TYPE_DEPOSIT_COLLATERAL,
    TX_TYPE_EXCLUDED,
    TX_TYPE_GIFT_RECEIVED,
    TX_TYPE_INCOME,
    TX_TYPE_LP_DEPOSIT,
    TX_TYPE_LP_STAKE,
    TX_TYPE_LP_UNSTAKE,
    TX_TYPE_LP_WITHDRAW,
    TX_TYPE_REPAY,
    TX_TYPE_SOL_TRANSFER_SELF,
    TX_TYPE_SPEND,
    TX_TYPE_STAKE,
    TX_TYPE_STAKING,
    TX_TYPE_TRADE,
    TX_TYPE_TRANSFER,
    TX_TYPE_UNKNOWN,
    TX_TYPE_UNSTAKE,
    TX_TYPE_WITHDRAW_COLLATERAL,
    TX_TYPE_REALIZED_PNL,
)
from staketaxcsv.settings_csv import DONATION_WALLETS
CUR_USD = "USD"


def make_swap_tx(txinfo, sent_amount, sent_currency, received_amount, received_currency,
                 txid=None, empty_fee=False, z_index=0):
    return _make_tx_exchange(txinfo, sent_amount, sent_currency, received_amount, received_currency,
                             TX_TYPE_TRADE, txid, empty_fee, z_index)


def make_airdrop_tx(txinfo, reward_amount, reward_currency, txid=None, empty_fee=False, z_index=0):
    return _make_tx_received(
        txinfo, reward_amount, reward_currency, TX_TYPE_AIRDROP, txid, empty_fee=empty_fee, z_index=z_index)


def make_income_tx(txinfo, income_amount, income_currency, txid=None, empty_fee=False, z_index=0):
    return _make_tx_received(
        txinfo, income_amount, income_currency, TX_TYPE_INCOME, txid, empty_fee=empty_fee, z_index=z_index)


def make_buy_tx(txinfo, received_amount, received_currency, txid=None, empty_fee=False, z_index=0, note=""):
    """ Single-sided acquisition valued at the market price of the day: crypto received whose
    cost leg is unavailable. Recorded as GIFT_RECEIVED (-> BittyTax "Gift-Received") so it is
    market-valued and added to the cost basis, without being taxed as income or treated as a
    zero-cost transfer-in. A single-sided "Trade" cannot be used (BittyTax rejects a Trade with
    no sell leg). `note` explains the Gift-Received label.

    ⚠ Market valuation is fiscally correct ONLY for a *gratuitous* acquisition with no
    documented value (gift, passive fork — CGI 150 VH bis III-B 2nd para.). It must NOT be used
    for an *onerous* buy whose cost is unknown: French law then deems the cost basis nil
    (BOFiP BOI-RPPM-PVBMC-30-20 §90), not market. For a documented onerous cost, use
    make_fiat_buy_tx instead. Currently unused (kept for a future gratuitous case);
    cf. ADR 0004 / ADR 0013. """
    row = _make_tx_received(
        txinfo, received_amount, received_currency, TX_TYPE_GIFT_RECEIVED, txid,
        empty_fee=empty_fee, z_index=z_index)
    if note:
        row.comment = (note + " " + row.comment).strip() if row.comment else note
    return row


def make_fiat_sale_tx(txinfo, sent_amount, sent_currency, fiat_amount, fiat_currency,
                      txid=None, empty_fee=False, z_index=0, note=""):
    """ Sale of crypto against fiat received off-chain (e.g. an OTC sale paid by PayPal).
    On-chain only the crypto leg is visible (an outbound transfer); the fiat proceeds are
    known from off-chain context. Recorded as a TRADE (sell crypto / buy fiat) so it is a
    taxable cession valued at the exact fiat amount received, instead of an unpaired
    transfer-out. `note` documents the off-chain counterparty. """
    row = _make_tx_exchange(
        txinfo, sent_amount, sent_currency, fiat_amount, fiat_currency, TX_TYPE_TRADE, txid,
        empty_fee=empty_fee, z_index=z_index)
    if note:
        row.comment = (note + " " + row.comment).strip() if row.comment else note
    return row


def make_fiat_buy_tx(txinfo, received_amount, received_currency, fiat_amount, fiat_currency,
                     txid=None, empty_fee=False, z_index=0, note=""):
    """ Acquisition of crypto against fiat paid off-chain, whose real cost is known from a
    contemporaneous receipt (e.g. a card on-ramp documented by an invoice). On-chain only the
    crypto leg is visible (an inbound transfer); the fiat cost is known off-chain. Recorded as
    a TRADE (buy crypto / sell fiat) so the acquisition enters the cost basis at the EXACT fiat
    amount paid, instead of a market estimate. This is the correct, fiscally-safest treatment
    for a documented onerous acquisition (real EUR cost = "prix effectif d'acquisition",
    CGI 150 VH bis III-B). `note` documents the off-chain receipt. Cf. ADR 0013. """
    row = _make_tx_exchange(
        txinfo, fiat_amount, fiat_currency, received_amount, received_currency, TX_TYPE_TRADE, txid,
        empty_fee=empty_fee, z_index=z_index)
    if note:
        row.comment = (note + " " + row.comment).strip() if row.comment else note
    return row


def make_reward_tx(txinfo, reward_amount, reward_currency, txid=None, empty_fee=False, z_index=0):
    """ Staking reward transaction """
    return _make_tx_received(txinfo, reward_amount, reward_currency, TX_TYPE_STAKING, txid, empty_fee, z_index=z_index)


def make_spend_tx(txinfo, sent_amount, sent_currency, z_index=0):
    return _make_tx_sent(txinfo, sent_amount, sent_currency, TX_TYPE_SPEND, z_index=z_index)


def make_spend_fee_tx(txinfo, fee_amount, fee_currency, z_index=0):
    return _make_tx_sent(txinfo, fee_amount, fee_currency, TX_TYPE_SPEND, z_index=z_index, empty_fee=True)


def make_transfer_out_tx(txinfo, sent_amount, sent_currency, dest_address=None, z_index=0):
    if dest_address and dest_address in DONATION_WALLETS:
        return make_spend_tx(txinfo, sent_amount, sent_currency, z_index)
    else:
        return _make_tx_sent(txinfo, sent_amount, sent_currency, TX_TYPE_TRANSFER, z_index=z_index)


def make_transfer_in_tx(txinfo, received_amount, received_currency, z_index=0):
    # Adjust to no fees for transfer-in transactions
    txinfo.fee = ""
    txinfo.fee_currency = ""

    if DONATION_WALLETS and txinfo.wallet_address in DONATION_WALLETS:
        row = _make_tx_received(txinfo, received_amount, received_currency, TX_TYPE_INCOME, z_index=z_index)
        row.comment = "donation " + row.comment
        return row
    else:
        return _make_tx_received(txinfo, received_amount, received_currency, TX_TYPE_TRANSFER, z_index=z_index)


def make_transfer_self(txinfo):
    return make_simple_tx(txinfo, TX_TYPE_SOL_TRANSFER_SELF)


def make_lp_deposit_tx(txinfo, sent_amount, sent_currency, lp_amount, lp_currency, txid=None, empty_fee=False,
                       z_index=0):
    row = _make_tx_exchange(
        txinfo, sent_amount, sent_currency, lp_amount, lp_currency, TX_TYPE_LP_DEPOSIT, txid, empty_fee,
        z_index=z_index)
    row.comment = "lp_deposit " + txinfo.comment
    return row


def make_lp_withdraw_tx(txinfo, lp_amount, lp_currency, received_amount, received_currency, txid=None,
                        empty_fee=False, z_index=0):
    row = _make_tx_exchange(
        txinfo, lp_amount, lp_currency, received_amount, received_currency,
        TX_TYPE_LP_WITHDRAW, txid, empty_fee, z_index)
    row.comment = "lp_withdraw " + txinfo.comment
    return row


def make_lp_stake_tx(txinfo, lp_amount, lp_currency, empty_fee=False, z_index=0):
    return _make_tx_sent(txinfo, lp_amount, lp_currency, TX_TYPE_LP_STAKE, empty_fee=empty_fee, z_index=z_index)


def make_lp_unstake_tx(txinfo, lp_amount, lp_currency, z_index=0):
    return _make_tx_received(txinfo, lp_amount, lp_currency, TX_TYPE_LP_UNSTAKE, z_index=z_index)


def make_stake_tx(txinfo, lp_amount, lp_currency, empty_fee=False, z_index=0):
    return _make_tx_sent(txinfo, lp_amount, lp_currency, TX_TYPE_STAKE, empty_fee=empty_fee, z_index=z_index)


def make_unstake_tx(txinfo, lp_amount, lp_currency, empty_fee=False, z_index=0):
    return _make_tx_received(txinfo, lp_amount, lp_currency, TX_TYPE_UNSTAKE, empty_fee=empty_fee, z_index=z_index)


def make_deposit_collateral_tx(txinfo, sent_amount, sent_currency, z_index=0):
    return _make_tx_sent(txinfo, sent_amount, sent_currency, TX_TYPE_DEPOSIT_COLLATERAL, z_index=z_index)


def make_withdraw_collateral_tx(txinfo, received_amount, received_currency, empty_fee=False, z_index=0):
    return _make_tx_received(
        txinfo, received_amount, received_currency, TX_TYPE_WITHDRAW_COLLATERAL, empty_fee=empty_fee, z_index=z_index)


def make_liquidate_tx(txinfo, sent_amount, sent_currency, received_amount, received_currency,
                      txid=None, empty_fee=False, z_index=0):
    return _make_tx_exchange(
        txinfo, sent_amount, sent_currency, received_amount, received_currency, TX_TYPE_TRADE, txid, empty_fee, z_index)


def make_borrow_tx(txinfo, received_amount, received_currency, empty_fee=False, z_index=0):
    row = _make_tx_received(
        txinfo, received_amount, received_currency, TX_TYPE_BORROW, empty_fee=empty_fee, z_index=z_index)
    row.comment = "borrow " + txinfo.comment
    return row


def make_repay_tx(txinfo, sent_amount, sent_currency, z_index=0):
    row = _make_tx_sent(txinfo, sent_amount, sent_currency, TX_TYPE_REPAY, z_index=z_index)
    row.comment = "repay " + txinfo.comment
    return row


def make_simple_tx(txinfo, tx_type, z_index=0, empty_fee=False):
    fee = "" if empty_fee else txinfo.fee
    fee_currency = txinfo.fee_currency if fee else ""

    row = Row(
        timestamp=txinfo.timestamp,
        tx_type=tx_type,
        received_amount="",
        received_currency="",
        sent_amount="",
        sent_currency="",
        fee=fee,
        fee_currency=fee_currency,
        exchange=txinfo.exchange,
        wallet_address=txinfo.wallet_address,
        txid=txinfo.txid,
        url=txinfo.url,
        z_index=z_index,
        comment=txinfo.comment
    )
    return row


def make_unknown_tx(txinfo, z_index=0, empty_fee=False):
    return make_simple_tx(txinfo, TX_TYPE_UNKNOWN, z_index, empty_fee)


def make_unknown_tx_with_transfer(txinfo, sent_amount, sent_currency, received_amount,
                                  received_currency, empty_fee=False, z_index=0):
    return _make_tx_exchange(
        txinfo, sent_amount, sent_currency, received_amount, received_currency, TX_TYPE_UNKNOWN,
        empty_fee=empty_fee, z_index=z_index
    )


def make_excluded_tx(txinfo):
    return make_simple_tx(txinfo, TX_TYPE_EXCLUDED)


def make_excluded_tx_with_transfer(txinfo, sent_amount, sent_currency, received_amount,
                                  received_currency, empty_fee=False, z_index=0):
    return _make_tx_exchange(
        txinfo, sent_amount, sent_currency, received_amount, received_currency, TX_TYPE_EXCLUDED,
        empty_fee=empty_fee, z_index=z_index
    )


# perps realized profit and loss tx (result from selling a position in perpetuals)
def make_perp_pnl_tx(txinfo, net_gain_or_loss):
    if net_gain_or_loss >= 0:
        return _make_tx_exchange(txinfo, "", "", net_gain_or_loss, CUR_USD, TX_TYPE_REALIZED_PNL)
    elif net_gain_or_loss < 0:
        return _make_tx_exchange(txinfo, -net_gain_or_loss, CUR_USD, "", "", TX_TYPE_REALIZED_PNL)


def _make_tx_received(txinfo, received_amount, received_currency, tx_type, txid=None, empty_fee=False, z_index=0):
    txid = txid if txid else txinfo.txid
    fee = "" if empty_fee else txinfo.fee
    fee_currency = txinfo.fee_currency if fee else ""

    row = Row(
        timestamp=txinfo.timestamp,
        tx_type=tx_type,
        received_amount=received_amount,
        received_currency=received_currency,
        sent_amount="",
        sent_currency="",
        fee=fee,
        fee_currency=fee_currency,
        exchange=txinfo.exchange,
        wallet_address=txinfo.wallet_address,
        txid=txid,
        url=txinfo.url,
        z_index=z_index,
        comment=txinfo.comment
    )
    return row


def _make_tx_sent(txinfo, sent_amount, sent_currency, tx_type, empty_fee=False, z_index=0):
    fee = "" if empty_fee else txinfo.fee
    fee_currency = txinfo.fee_currency if fee else ""

    row = Row(
        timestamp=txinfo.timestamp,
        tx_type=tx_type,
        received_amount="",
        received_currency="",
        sent_amount=sent_amount,
        sent_currency=sent_currency,
        fee=fee,
        fee_currency=fee_currency,
        exchange=txinfo.exchange,
        wallet_address=txinfo.wallet_address,
        txid=txinfo.txid,
        url=txinfo.url,
        z_index=z_index,
        comment=txinfo.comment
    )
    return row


def _make_tx_exchange(txinfo, sent_amount, sent_currency, received_amount, received_currency, tx_type,
                      txid=None, empty_fee=False, z_index=0):
    txid = txid if txid else txinfo.txid
    fee = "" if empty_fee else txinfo.fee
    fee_currency = txinfo.fee_currency if fee else ""

    row = Row(
        timestamp=txinfo.timestamp,
        tx_type=tx_type,
        received_amount=received_amount,
        received_currency=received_currency,
        sent_amount=sent_amount,
        sent_currency=sent_currency,
        fee=fee,
        fee_currency=fee_currency,
        exchange=txinfo.exchange,
        wallet_address=txinfo.wallet_address,
        txid=txid,
        url=txinfo.url,
        z_index=z_index,
        comment=txinfo.comment
    )
    return row


def ingest_rows(exporter, txinfo, rows):
    """ Utility function to add multiple rows to CSV for single transaction. """
    if len(rows) == 0:
        # No transactions.  Just make a "spend fee" row.
        if txinfo.fee:
            row = make_spend_fee_tx(txinfo, txinfo.fee, txinfo.fee_currency)
            row.comment = "tx fee"
            rows.append(rows)
    else:
        for i, row in enumerate(rows):
            # Apply transaction fee to first row's fee column only
            if i == 0:
                row.fee = txinfo.fee
                row.fee_currency = txinfo.fee_currency
            else:
                row.fee = ""
                row.fee_currency = ""

            exporter.ingest_row(row)
