import hmac
import hashlib
import json
from collections import OrderedDict

class SodexAuthMainnet:
    @staticmethod
    def create_signature(private_key: str, method: str, params: dict, api_nonce: int) -> str:
        """
        Mainnet uses HMAC SHA256 signature using SODEX_PRIVATE_KEY.
        The payload to sign typically includes nonce, method, and JSON body.
        """
        # Ensure ordered dictionary for consistent JSON serialization
        if not isinstance(params, OrderedDict):
            params = OrderedDict(params)
            
        compact_json = json.dumps(params, separators=(',', ':'))
        
        # Build payload string - standard approach: nonce + method + json_body
        payload_string = f"{api_nonce}{method}{compact_json}"
        
        # Create HMAC SHA256 signature
        signature = hmac.new(
            private_key.encode('utf-8'),
            payload_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
