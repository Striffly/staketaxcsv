import logging

from staketaxcsv.common.ErrorCounter import ErrorCounter
from staketaxcsv.sol import constants as co
from staketaxcsv.sol.config_sol import localconfig
from staketaxcsv.sol.handle_account_misc import (
    handle_close_account_tx,
    handle_init_account_tx,
    is_close_account_tx,
    is_init_account_tx,
    handle_claim_staking_tip,
)
from staketaxcsv.sol.handle_jupiter import (
    handle_jupiter_aggregator_v1,
    handle_jupiter_aggregator_v2,
    handle_jupiter_aggregator_v3,
    handle_jupiter_aggregator_v4,
    handle_jupiter_aggregator_v6,
)
from staketaxcsv.sol.handle_jupiter_airdrop import handle_wen_airdrop
from staketaxcsv.sol.handle_jupiter_dca import handle_jupiter_dca
from staketaxcsv.sol.handle_jupiter_limit import handle_jupiter_limit
from staketaxcsv.sol.handle_jupiter_limit_v2 import handle_jupiter_limit_v2
from staketaxcsv.sol.handle_jupiter_perp import handle_jupiter_perp
from staketaxcsv.sol.handle_marinade import (
    handle_marinade, is_marinade_native_staking_create_tx, handle_marinade_native_staking_create_tx)
from staketaxcsv.sol.handle_metaplex import handle_metaplex, handle_nft_mint, is_nft_mint
from staketaxcsv.sol.handle_nft_market import get_nft_program, handle_nft_exchange
from staketaxcsv.sol.handle_notimestamp import handle_notimestamp_tx, is_notimestamp_tx
from staketaxcsv.sol.handle_orca import handle_orca_swap_v2
from staketaxcsv.sol.handle_raydium_lp import handle_raydium_lp_v2, handle_raydium_lp_v3, handle_raydium_lp_v4
from staketaxcsv.sol.handle_raydium_stake import handle_raydium_stake, handle_raydium_stake_v4, handle_raydium_stake_v5
from staketaxcsv.sol.handle_saber import handle_saber, handle_saber_farm_ssf, handle_saber_stable_swap
from staketaxcsv.sol.handle_serumv3 import handle_serumv3
from staketaxcsv.sol.handle_simple import (
    handle_simple_tx,
    handle_unknown,
    handle_unknown_detect_transfers,
    is_simple_tx,
)
from staketaxcsv.sol.handle_swap_v2 import handle_program_swap_v2
from staketaxcsv.sol.handle_transfer import handle_transfer, is_transfer
from staketaxcsv.sol.handle_unknowns import handle_2kd, handle_djv
from staketaxcsv.sol.handle_pumpfun import handle_pumpfun
from staketaxcsv.sol.handle_raydium_route import handle_raydium_route
from staketaxcsv.sol.handle_degen_crash import handle_degen_crash
from staketaxcsv.sol.handle_okx_dex import handle_okx_dex
from staketaxcsv.sol.handle_token_close import handle_token_close
from staketaxcsv.sol.handle_vote import handle_vote
from staketaxcsv.sol.handle_wormhole import handle_wormhole
from staketaxcsv.sol.parser import parse_tx

# ── Rapport de qualité des données ─────────────────────────────────────────
_unknown_tx_details = []   # [{txid, program_ids, balance_changes}]
_total_tx_processed = 0


def reset_tracker():
    global _unknown_tx_details, _total_tx_processed
    _unknown_tx_details = []
    _total_tx_processed = 0


def print_unknown_tx_report(wallet_address):
    """Imprime un rapport lisible sur la qualité des données générées."""
    impactful = [d for d in _unknown_tx_details if d["balance_changes"]]
    harmless  = [d for d in _unknown_tx_details if not d["balance_changes"]]

    sep = "=" * 72
    print(f"\n{sep}")
    print(f"RAPPORT DE QUALITÉ DES DONNÉES — Wallet : {wallet_address}")
    print(sep)
    print(f"  Transactions analysées                         : {_total_tx_processed}")
    print(f"  Transactions non reconnues (unknown_sol_tx)    : {len(_unknown_tx_details)}")
    print(f"    → sans impact sur le solde (NFT, vote…)     : {len(harmless)}")
    print(f"    → avec impact sur le solde NON CAPTURÉ      : {len(impactful)}")

    if impactful:
        print("\n  /!\\ TRANSACTIONS AVEC IMPACT MANQUANTES :")
        for d in impactful:
            print(f"    txid     : {d['txid']}")
            print(f"    programs : {d['program_ids']}")
            print(f"    delta    : {d['balance_changes']}")
            print(f"    url      : https://solana.fm/tx/{d['txid']}")
            print()
        print("  VERDICT : Le CSV NE reflète PAS complètement l'état du portefeuille.")
        print("            Les transactions listées ci-dessus sont absentes du registre.")
    else:
        print("\n  VERDICT : OK — Toutes les transactions ayant un impact sur le solde")
        print("            ont été capturées. Le CSV reflète fidèlement le portefeuille.")
    print(f"{sep}\n")
# ───────────────────────────────────────────────────────────────────────────


def process_tx(wallet_info, exporter, txid, data):
    global _total_tx_processed
    _total_tx_processed += 1
    txinfo = parse_tx(txid, data, wallet_info)

    try:
        if not txinfo:
            return
        program_ids = txinfo.program_ids

        if is_notimestamp_tx(txinfo):
            handle_notimestamp_tx(exporter, txinfo)

        # Bridges
        elif co.PROGRAMID_WORMHOLE in program_ids or co.PROGRAMID_WORMHOLE2 in program_ids:
            handle_wormhole(exporter, txinfo)

        # Serum programs
        elif co.PROGRAMID_SWAP_V2 in program_ids:
            handle_program_swap_v2(exporter, txinfo)
        elif co.PROGRAMID_SERUM_V3 in program_ids:
            handle_serumv3(exporter, txinfo)

        # Marinade Finance
        elif co.PROGRAMID_MARINADE in program_ids or co.PROGRAMID_MARINADE_V2 in program_ids:
            handle_marinade(exporter, txinfo)
        elif is_marinade_native_staking_create_tx(txinfo):
            handle_marinade_native_staking_create_tx(wallet_info, exporter, txinfo)

        # Unknown programs
        elif co.PROGRAMID_UNKNOWN_DJV in program_ids:
            handle_djv(exporter, txinfo)
        elif co.PROGRAMID_UNKNOWN_2KD in program_ids:
            handle_2kd(exporter, txinfo)

        # Pump.fun bonding curve
        elif co.PROGRAMID_PUMPFUN in program_ids:
            handle_pumpfun(exporter, txinfo)

        # Raydium AMM Routing
        elif co.PROGRAMID_RAYDIUM_ROUTE in program_ids:
            handle_raydium_route(exporter, txinfo)

        # Degen Crash gambling
        elif co.PROGRAMID_DEGEN_CRASH in program_ids:
            handle_degen_crash(exporter, txinfo)

        # OKX DEX aggregator (must precede is_simple_tx: its createAccountWithSeed
        # for the wSOL account would otherwise be misread as _STAKING_CREATE)
        elif co.PROGRAMID_OKX_DEX in program_ids:
            handle_okx_dex(exporter, txinfo)

        # Token burn / close account services (rent refund)
        elif co.PROGRAMID_TOKEN_BURNER in program_ids:
            handle_token_close(exporter, txinfo)

        # Raydium programs
        elif co.PROGRAMID_RAYDIUM_LP_V2 in program_ids:
            handle_raydium_lp_v2(exporter, txinfo)
        elif co.PROGRAMID_RAYDIUM_LP_V3 in program_ids:
            handle_raydium_lp_v3(exporter, txinfo)
        elif co.PROGRAMID_RAYDIUM_LP_V4 in program_ids:
            handle_raydium_lp_v4(exporter, txinfo)
        elif co.PROGRAMID_RAYDIUM_STAKE in program_ids:
            handle_raydium_stake(exporter, txinfo)
        elif co.PROGRAMID_RAYDIUM_STAKE_V4 in program_ids:
            handle_raydium_stake_v4(exporter, txinfo)
        elif co.PROGRAMID_RAYDIUM_STAKE_V5 in program_ids:
            handle_raydium_stake_v5(exporter, txinfo)

        # Orca programs
        elif co.PROGRAMID_ORCA_SWAP_V2 in program_ids or co.PROGRAMID_ORCA_SWAP_WHIRL in program_ids:
            handle_orca_swap_v2(exporter, txinfo)

        # Saber programs
        elif co.PROGRAMID_SABER in program_ids:
            handle_saber(exporter, txinfo)
        elif co.PROGRAMID_SABER_STABLE_SWAP in program_ids:
            handle_saber_stable_swap(exporter, txinfo)
        elif co.PROGRAMID_SABER_FARM_SSF in program_ids:
            handle_saber_farm_ssf(exporter, txinfo)

        # ### Jupiter programs

        # important that these are before jupiter aggregator programs
        elif co.PROGRAMID_JUPITER_LIMIT in program_ids:
            handle_jupiter_limit(exporter, txinfo)
        elif co.PROGRAMID_JUPITER_LIMIT_V2 in program_ids:
            handle_jupiter_limit_v2(exporter, txinfo)
        elif co.PROGRAMID_JUPITER_DCA_V6 in program_ids:
            handle_jupiter_dca(exporter, txinfo)
        elif co.PROGRAMID_JUPITER_PERPERTUAL in program_ids:
            handle_jupiter_perp(exporter, txinfo)

        elif co.PROGRAMID_JUPITER_AGGREGATOR_V1 in program_ids:
            handle_jupiter_aggregator_v1(exporter, txinfo)
        elif co.PROGRAMID_JUPITER_AGGREGATOR_V2 in program_ids:
            handle_jupiter_aggregator_v2(exporter, txinfo)
        elif co.PROGRAMID_JUPITER_AGGREGATOR_V3 in program_ids:
            handle_jupiter_aggregator_v3(exporter, txinfo)
        elif co.PROGRAMID_JUPITER_AGGREGATOR_V4 in program_ids:
            handle_jupiter_aggregator_v4(exporter, txinfo)
        elif co.PROGRAMID_JUPITER_AGGREGATOR_V6 in program_ids:
            handle_jupiter_aggregator_v6(exporter, txinfo)
        elif co.PROGRAMID_JUPITER_WEN_AIRDROP in program_ids:
            handle_wen_airdrop(exporter, txinfo)

        ###

        # Metaplex NFT Candy Machinine program
        elif co.PROGRAMID_METAPLEX_CANDY in program_ids:
            handle_metaplex(exporter, txinfo)

        # SPL Token-only ops (no business program besides ComputeBudget) — fee-only
        elif (set(program_ids) - {co.PROGRAMID_COMPUTE_BUDGET}) == {co.PROGRAMID_TOKEN_ACCOUNTS}:
            handle_unknown_detect_transfers(exporter, txinfo)

        # Metaplex Bubblegum (compressed NFTs) — fee-only, no fungible asset transfer
        elif co.PROGRAMID_METAPLEX_BUBBLEGUM in program_ids:
            handle_unknown_detect_transfers(exporter, txinfo)

        # NFT marketplace transactions
        elif get_nft_program(txinfo):
            handle_nft_exchange(exporter, txinfo)

        # NFT transactions
        elif is_nft_mint(txinfo):
            handle_nft_mint(exporter, txinfo)

        # staking account claim transaction
        elif (co.PROGRAMID_CLAIM_STAKING_TIP in program_ids or co.PROGRAMID_CLAIM_STAKING_TIP_2 in program_ids):
            handle_claim_staking_tip(exporter, txinfo)

        # Other
        elif co.PROGRAMID_VOTE in program_ids:
            handle_vote(exporter, txinfo)
        elif is_simple_tx(txinfo):
            handle_simple_tx(exporter, txinfo)
        elif is_init_account_tx(txinfo):
            handle_init_account_tx(exporter, txinfo)
        elif is_transfer(txinfo):
            handle_transfer(exporter, txinfo)
        elif is_close_account_tx(txinfo):
            handle_close_account_tx(exporter, txinfo)

        else:
            handle_unknown_detect_transfers(exporter, txinfo)
            ErrorCounter.increment("unknown_sol_tx", txid)
            balance_changes = txinfo.balance_changes_wallet or {}
            _unknown_tx_details.append({
                "txid": txid,
                "program_ids": txinfo.program_ids,
                "instruction_types": txinfo.instruction_types,
                "balance_changes": balance_changes,
            })
            logging.info(
                "unknown_sol_tx details — txid=%s | program_ids=%s | instruction_types=%s | "
                "balance_changes_wallet=%s | url=https://solana.fm/tx/%s",
                txid, txinfo.program_ids, txinfo.instruction_types,
                balance_changes, txid,
            )

    except Exception as e:
        logging.error("Exception when handling txid=%s, exception=%s", txid, str(e))
        ErrorCounter.increment("exception", txid)
        handle_unknown_detect_transfers(exporter, txinfo)

        if localconfig.debug:
            raise e

    return txinfo
