import staketaxcsv.sol.util_sol
from staketaxcsv.common.make_tx import (
    make_airdrop_tx,
    make_buy_tx,
    make_fiat_sale_tx,
    make_transfer_in_tx,
    make_transfer_out_tx,
)
from staketaxcsv.settings_csv import SOL_OVERRIDES
from staketaxcsv.sol.constants import CURRENCY_SOL, INSTRUCT_TRANSFERCHECK, INSTRUCT_TRANSFERCHECKED

# Below this many SOL, an unsolicited inbound transfer is treated as spam "dust"
# (address-poisoning airdrops of 1-100 lamports), not an internal transfer. Rationale:
#   - fiscally (FR 150 VH bis): a dust airdrop has NO contrepartie -> not a BNC revenu;
#     valued at the market price of the day (~0 EUR, rounded to 0 at the pta), conforme au
#     "repute-acquis-pour-valeur-nulle" du BOFiP (BOI-RPPM-PVBMC-30-20 §90). It IS a real
#     in-kind receipt, so it must stay recorded (not erased) — it is just NOT a transfer.
#   - mechanically: typing it as a Deposit asserts "internal transfer in" and creates a
#     spurious POSITIVE transfers_mismatch (no matching Withdrawal exists — it came from a
#     spammer, not from one of my wallets). Airdrop credits the balance WITHOUT touching the
#     mismatch counter (audit.py reacts only to DEPOSIT/WITHDRAWAL).
# Threshold kept deliberately low so it can only ever catch incontestable dust. Observed
# here: real internal SOL transfers are all >= 0.11 SOL; the largest spam dust is 1e-5 SOL.
# 2e-5 SOL (~0.003 EUR) sits ~x2 above the largest dust and ~x5000 below the smallest real
# transfer — no misclassification either way. Only applies to SOL (CURRENCY_SOL guard); a
# per-asset threshold would be needed before extending this to assets like BTC, where 1e-4
# is a routine legitimate amount, not dust.
SOL_DUST_AIRDROP_THRESHOLD = 0.00002


def is_transfer(txinfo):
    instruction_types = txinfo.instruction_types
    log_instructions = txinfo.log_instructions

    # Check for transferCheck or transferChecked
    for instruction_type, program in instruction_types:
        if instruction_type in [INSTRUCT_TRANSFERCHECK, INSTRUCT_TRANSFERCHECKED]:
            return True

    if "Transfer" in log_instructions or ("transfer", "system") in instruction_types:
        # Verify no instructions except transfer or initialize/create/close account
        for instruction in log_instructions:
            if instruction not in ["Transfer", "InitializeAccount", "CloseAccount", "transfer", "system"]:
                return False
        return True

    return False


def handle_transfer(exporter, txinfo):
    txid = txinfo.txid
    override = SOL_OVERRIDES.get(txid)
    transfers_in, transfers_out, _ = txinfo.transfers_net

    if len(transfers_out) == 1 and len(transfers_in) == 0:
        amount, currency, _, dest = transfers_out[0]

        # For SOL transfers, adjust fee from zero to non-zero if applicable
        if currency == CURRENCY_SOL and txinfo.fee == "" and txinfo.fee_blockchain > 0:
            txinfo.fee = txinfo.fee_blockchain
            amount -= txinfo.fee_blockchain

        if override and override["type"] == "fiat_sale":
            # Outbound transfer that is actually a sale against fiat received off-chain
            # (e.g. paid by PayPal). Record as a taxable cession at the exact fiat amount.
            # See datas/sol_overrides.csv (loaded via STAKETAX_SOL_OVERRIDES_FILE).
            row = make_fiat_sale_tx(
                txinfo, amount, currency,
                float(override["amount"]), override["currency"], note=override["note"])
        else:
            row = make_transfer_out_tx(txinfo, amount, currency, dest)
        exporter.ingest_row(row)
    elif len(transfers_in) == 1 and len(transfers_out) == 0:
        amount, currency, _, _ = transfers_in[0]
        if override and override["type"] == "acquisition":
            # Withdrawal from a CEX account we no longer control (e.g. Bitstamp): the original
            # cost basis is lost, so record it as an acquisition valued at the market price of
            # the day instead of a (zero-cost) transfer-in.
            # See datas/sol_overrides.csv (loaded via STAKETAX_SOL_OVERRIDES_FILE).
            row = make_buy_tx(txinfo, amount, currency, note=override["note"])
        elif currency == CURRENCY_SOL and amount < SOL_DUST_AIRDROP_THRESHOLD:
            # Unsolicited SOL dust (spam/address-poisoning airdrop): a real in-kind receipt
            # without contrepartie, NOT an internal transfer. Airdrop (vs transfer-in) keeps it
            # recorded at ~0 EUR without creating a spurious positive transfers_mismatch.
            # See SOL_DUST_AIRDROP_THRESHOLD above.
            row = make_airdrop_tx(txinfo, amount, currency)
            row.comment = ("spam_dust airdrop non sollicite (address poisoning) " + (row.comment or "")).strip()
        else:
            row = make_transfer_in_tx(txinfo, amount, currency)
        exporter.ingest_row(row)
    else:
        raise Exception(f"Bad condition in handle_transfer(), txid={txid}")
