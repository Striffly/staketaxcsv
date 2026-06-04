import logging
from json import JSONDecodeError

from staketaxcsv.sol.api_rpc import RpcAPI
from staketaxcsv.sol.constants import CURRENCY_SOL, MILLION, PROGRAMID_STAKE

FEE_THRESHOLD = 0.03

# Cache for storing results of previous is_staking_account() calls
_is_staking_account_cache = {}


def amount_currency(txinfo, amount_string, currency_address):
    if currency_address in txinfo.mints:
        currency = txinfo.mints[currency_address]["currency"]
        decimals = txinfo.mints[currency_address]["decimals"]

        amount = float(amount_string) / (10 ** decimals)
        return amount, currency
    else:
        logging.warning("amount_currency(): currency_address=%s not found.  Using guesstimate.", currency_address)

        amount = float(amount_string) / MILLION
        return amount, currency_address


def detect_fees(_transfers_in, _transfers_out):
    """ Moves small SOL transfer out amount from into fee """
    fee = ""

    # Detect SOL small transfers out and move into fee
    transfers_out = []
    for transfer_out in _transfers_out:
        amount, currency, source, destination = transfer_out

        if currency == CURRENCY_SOL and amount < FEE_THRESHOLD:
            fee = amount
        else:
            transfers_out.append(transfer_out)

    return _transfers_in, transfers_out, fee


def swap_legs_from_raw(txinfo):
    """ Reconstruct the (sent, received) legs of a 2-sided swap from the RAW
    transfers (txinfo.transfers), removing ONLY the true on-chain gas
    (txinfo.fee_blockchain) from the SOL out leg.

    Rationale: detect_fees() folds ANY SOL out below FEE_THRESHOLD (0.03 SOL,
    ~6 EUR) into "fee". For small memecoin buys/sells (pump.fun, Raydium route)
    the actual purchase amount is below that threshold, so the SOL leg gets
    wrongly swallowed and the swap collapses to a single leg. Here we keep the
    SOL leg and net out only the real network fee, so the swap stays balanced
    and fiscally faithful (crypto<->crypto swap, "sursis").

    Returns (sent_amount, sent_currency, received_amount, received_currency)
    when exactly one asset moves in and one moves out, else None.
    """
    transfers_in, transfers_out, _ = txinfo.transfers

    # Net by currency (raw, before detect_fees), keeping the SOL gas in place.
    net = {}
    for amount, currency, _, _ in transfers_in:
        net[currency] = net.get(currency, 0) + amount
    for amount, currency, _, _ in transfers_out:
        net[currency] = net.get(currency, 0) - amount

    # Remove ONLY the true on-chain fee from the SOL leg (gas is always paid in SOL).
    if CURRENCY_SOL in net and txinfo.fee_blockchain:
        net[CURRENCY_SOL] += txinfo.fee_blockchain  # net SOL is negative when SOL goes out

    legs_in = [(amt, cur) for cur, amt in net.items() if amt > 1e-12]
    legs_out = [(-amt, cur) for cur, amt in net.items() if amt < -1e-12]

    if len(legs_in) == 1 and len(legs_out) == 1:
        received_amount, received_currency = legs_in[0]
        sent_amount, sent_currency = legs_out[0]
        return sent_amount, sent_currency, received_amount, received_currency
    return None


def net_sol_movement_from_raw(txinfo):
    """ Net SOL moved by the wallet from RAW transfers, with ONLY the true on-chain
    gas (txinfo.fee_blockchain) removed. Use for one-sided SOL operations (e.g. a
    gambling bet/win) where detect_fees() would otherwise swallow a sub-threshold
    SOL amount into "fee" and lose the real economic movement.

    Returns a signed amount in SOL: negative = SOL left the wallet (bet/spend),
    positive = SOL entered (win), 0.0 if only gas moved.
    """
    transfers_in, transfers_out, _ = txinfo.transfers
    net = 0.0
    for amount, currency, _, _ in transfers_in:
        if currency == CURRENCY_SOL:
            net += amount
    for amount, currency, _, _ in transfers_out:
        if currency == CURRENCY_SOL:
            net -= amount
    if txinfo.fee_blockchain:
        net += txinfo.fee_blockchain  # add back gas: it is not part of the economic op
    return net


def calculate_fee(txinfo):
    """ Returns fee amount for transaction """
    _, transfers_out, _ = txinfo.transfers
    fee_total = 0

    for transfer_out in transfers_out:
        amount, currency, source, destination = transfer_out

        if currency == CURRENCY_SOL and amount < FEE_THRESHOLD:
            fee_total += amount

    if fee_total > 0:
        return fee_total
    else:
        return txinfo.fee_blockchain


def account_exists(wallet_address):
    data = RpcAPI.fetch_account(wallet_address)

    if "result" not in data:
        return False, False
    if "error" in data:
        return False, False

    try:
        owner = data["result"]["value"]["owner"]
        if owner == PROGRAMID_STAKE:
            return False, True
        else:
            return True, False
    except (JSONDecodeError, TypeError):
        return False, False


def is_staking_account(wallet_address):
    """Returns True if the address is a staking account, False otherwise, with caching."""
    if wallet_address in _is_staking_account_cache:
        return _is_staking_account_cache[wallet_address]

    _, is_staking = account_exists(wallet_address)
    _is_staking_account_cache[wallet_address] = is_staking
    return is_staking
