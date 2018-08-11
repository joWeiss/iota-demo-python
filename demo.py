#!/usr/bin/env python
from hashing_passwords import make_hash

from json import loads
from sys import exit
from typing import Dict

from iota import Iota, TryteString
from iota.filters import AddressNoChecksum
from pendulum import from_timestamp, now
from redis import StrictRedis


def extract_json(bundle) -> Dict:
    extracted_json = {}
    first_transaction = bundle[0]
    first_tryte_pair = (
        first_transaction.signature_message_fragment[0]
        + first_transaction.signature_message_fragment[1]
    )
    if first_tryte_pair != "OD":
        raise ValueError("No JSON found.")
    for transaction in bundle:
        fragment = transaction.signature_message_fragment
        try:
            extracted_json.update(loads(fragment.decode()))
        except ValueError as e:
            pass
    return extracted_json


def filter_transactions(iota, deposit_addr):
    transactions = iota.get_latest_inclusion(
        iota.find_transactions(addresses=[deposit_addr])["hashes"]
    )
    return filter(lambda t: transactions["states"][t], transactions["states"])


def check_payments(iota, transactions, addr):
    payments = {"bundles": []}
    bundles = iota.get_bundles(transactions)
    for t in bundles["bundles"][0]:
        trytes_addr = AddressNoChecksum()._apply(TryteString(addr))
        transaction_age = now() - from_timestamp(t.timestamp)
        if t.address == trytes_addr and transaction_age.in_minutes() < 5:
            print(
                f"[{from_timestamp(t.timestamp)}] Payment of {t.value}i found on receiving address {trytes_addr[:8]}..."
            )
            payments.update(iota.get_bundles(t.hash))
    if not payments.get("bundles"):
        print("No valid payments found.")
        exit(1)
    return payments


def update_auth(payload):
    username = payload.get("username")
    topic = payload.get("topic")
    password = make_hash(f"{username}-{topic}")
    redis = StrictRedis()
    redis.set("username")


def main():
    iota = Iota("https://potato.iotasalad.org:14265")
    receiving_addr = "MPUKMWNFTYFRLJDE9ZWJY9JPKVEIIKDOWANMJIHJJWPOINFRXKVLWOUHFCMCWLO9GAAWDRWGXMTKFCIZDDQTTHNERC"
    print("Successfully connected to remote IOTA node...")
    print("Searching for valid transactions...")
    payments = []
    for t in filter_transactions(iota, receiving_addr):
        payments.append(check_payments(iota, t, receiving_addr))
    print("Extracting payload...")
    for p in payments:
        payload = loads(extract_json(p))
        update_auth(payload)


if __name__ == "__main__":
    main()