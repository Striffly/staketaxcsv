"""
Handler for Degen Crash gambling transactions.
Program: DEALERKFspSo5RoXNnKAhRPhTcvJeqeEgAgZsNSjCx5E

SOL out (bet placed / loss) → SPEND
SOL in  (win)               → INCOME

Note fiscale FR : les gains de jeux d'argent sont en principe exonérés d'impôt
pour les particuliers (art. 157 CGI). Ces lignes servent uniquement à maintenir
l'exactitude du solde SOL dans le registre ; l'utilisateur peut les exclure
manuellement si nécessaire.
"""
from staketaxcsv.common.make_tx import make_income_tx, make_spend_tx
from staketaxcsv.sol.handle_simple import handle_unknown_detect_transfers


def handle_degen_crash(exporter, txinfo):
    transfers_in, transfers_out, _ = txinfo.transfers_net

    if len(transfers_in) == 1 and len(transfers_out) == 0:
        # Gain : SOL reçu
        received_amount, received_currency, _, _ = transfers_in[0]
        row = make_income_tx(txinfo, received_amount, received_currency)
        row.comment = "gambling_win " + row.comment
        exporter.ingest_row(row)

    elif len(transfers_in) == 0 and len(transfers_out) == 1:
        # Perte : SOL envoyé
        sent_amount, sent_currency, _, _ = transfers_out[0]
        row = make_spend_tx(txinfo, sent_amount, sent_currency)
        row.comment = "gambling_bet " + row.comment
        exporter.ingest_row(row)

    else:
        handle_unknown_detect_transfers(exporter, txinfo)
