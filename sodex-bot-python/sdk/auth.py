import json
import time
from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3

class SodexAuth:
    @staticmethod
    def create_signature(private_key: str, method: str, params: dict, api_name: str, api_nonce: int, chain_id: int, api_public_key: str = None) -> str:
        from collections import OrderedDict
        # 1. PAYLOAD HASH FROM BYTES
        payload = OrderedDict([
            ("type", method),
            ("params", params)
        ])
        compact_json = json.dumps(payload, separators=(',', ':'))
        payload_bytes = compact_json.encode()
        payload_hash = Web3.keccak(payload_bytes)

        # 2. SODEX API STRUCT
        eip712_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "ExchangeAction": [
                    {"name": "payloadHash", "type": "bytes32"},
                    {"name": "nonce", "type": "uint64"},
                ],
            },
            "domain": {
                "name": "futures",
                "version": "1",
                "chainId": int(chain_id),
                "verifyingContract": "0x0000000000000000000000000000000000000000",
            },
            "primaryType": "ExchangeAction",
            "message": {
                "payloadHash": payload_hash,
                "nonce": int(api_nonce),
            },
        }

        # 3. SIGN EIP-712
        message = encode_typed_data(full_message=eip712_data)
        signed = Account.sign_message(message, private_key=private_key)
        
        # 4. RECOVER LOG
        recovered = Account.recover_message(message, signature=signed.signature)

        # 5. FORMAT 0x01 + r + s + v
        r = signed.r.to_bytes(32, 'big')
        s = signed.s.to_bytes(32, 'big')
        v = signed.v
        if v >= 27: v -= 27
        v_byte = v.to_bytes(1, 'big')
        
        signature_hex = "0x01" + r.hex() + s.hex() + v_byte.hex()
        return signature_hex

    @staticmethod
    def recover_address(private_key: str) -> str:
        return Account.from_key(private_key).address
