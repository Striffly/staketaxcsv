"""
Handler for Degen Crash gambling transactions.
Program: DEALERKFspSo5RoXNnKAhRPhTcvJeqeEgAgZsNSjCx5E

SOL out (bet placed / loss) → SPEND   (comment "gambling_bet")
SOL in  (win)               → INCOME  (comment "gambling_win")

Note fiscale FR (cf. docs/implementation-calcul-fiscal-fr.md §7) :
- la mise (SOL out) est une cession imposable 150 VH bis du SOL cédé ;
- le gain (SOL in) est exonéré d'IR (art. 92 CGI + jurisprudence CE), pris en
  pta à la valeur de marché. Conserver ces lignes pour l'exactitude du solde
  ET le calcul de plus-value.

Petites mises (< FEE_THRESHOLD = 0.03 SOL) : detect_fees() avale le SOL dans la
"fee", vidant transfers_net → la mise serait perdue. On reconstruit alors le
mouvement SOL net depuis les transferts bruts (net_sol_movement_from_raw), en ne
retirant que le vrai gas réseau.
"""
from staketaxcsv.common.make_tx import make_income_tx, make_spend_tx
from staketaxcsv.sol.constants import CURRENCY_SOL
from staketaxcsv.sol.handle_simple import handle_unknown_detect_transfers
from staketaxcsv.sol.util_sol import net_sol_movement_from_raw


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
        # transfers_net vide : la mise/le gain SOL (< 0.03) a été avalé en "fee".
        # On reconstruit le mouvement SOL net réel (gas exclu).
        net_sol = net_sol_movement_from_raw(txinfo)
        if net_sol < -1e-9:
            # mise jouée / perdue
            row = make_spend_tx(txinfo, -net_sol, CURRENCY_SOL)
            row.comment = "gambling_bet " + (txinfo.comment or "")
            exporter.ingest_row(row)
        elif net_sol > 1e-9:
            # gain
            row = make_income_tx(txinfo, net_sol, CURRENCY_SOL)
            row.comment = "gambling_win " + (txinfo.comment or "")
            exporter.ingest_row(row)
        else:
            handle_unknown_detect_transfers(exporter, txinfo)
