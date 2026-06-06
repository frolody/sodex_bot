# SoDEX Trading Bot - Developer Notes

## CRITICAL AUTHENTICATION RULES FOR AI AGENTS
**DO NOT IGNORE THIS SECTION UNDER ANY CIRCUMSTANCES.** 
This section documents the exact, hard-fought facts about how the SoDEX API authentication works. The user was 100% correct about this from the start. DO NOT attempt to rewrite the authentication logic, use HMAC, or use EVM Wallet Addresses as the API Key. 

### 1. The `chain_id` Trap (The Most Important Fact)
SoDEX has a highly unusual configuration for their `chain_id` in EIP-712 Typed Signatures. They intentionally **SWAPPED** the `chainId` compared to what you might expect or what is in the `.env` file:
*   **Mainnet (`mainnet-gw.sodex.dev`) MUST use `chain_id`: `286623`**
*   **Testnet (`testnet-gw.sodex.dev`) MUST use `chain_id`: `138565`**

If you use the `.env` `SODEX_CHAIN_ID` (which is `138565`) for Mainnet, the API will respond with `"API key not found"`. This is NOT an issue with the API Key or Secret; it is simply because the `chainId` in the EIP-712 domain payload is rejected. **Never change the `chain_id` assignment in `sdk/client.py` and `src/app/page.tsx`.**

### 2. X-API-Key is the API Key Name
When passing the HTTP header `X-API-Key`, the value **MUST** be the human-readable string name of the API key created on the dashboard (e.g., `FROLODY2_KEY` or `FROLODY_KEY`).
*   **DO NOT** use the public EVM wallet address (`0xefaf...`).
*   **DO NOT** use the public address of the API session key (`0x7894...`).

### 3. Signing Method (EIP-712)
SoDEX uses **EIP-712 (Web3 Typed Data Signing)** for all API requests.
*   **DO NOT** use HMAC SHA256. The API does not accept HMAC for normal trading actions. 
*   The `X-API-Sign` header must contain the `0x...` hex string produced by the EIP-712 signature.

### 4. The Private Key
The private key used to sign the EIP-712 payload for trading actions is the **API Key's Private Key** (a 32-byte ECDSA private key generated when creating the API key).
*   For Mainnet, the API Private Key happens to be `0x4b8a90ecdebc319ce787a5b233538f3a85beffab0206103af021b4098cab8163`.
*   This is the key stored in the `trading_data.db` database under `sodex_private_key`.

### Summary of Past Mistakes to Avoid
During development, previous AI agents wasted hours arguing with the user, assuming:
1.  That Mainnet used HMAC instead of EIP-712 (Wrong).
2.  That `X-API-Key` needed to be the Wallet Address (Wrong).
3.  That the user provided the wrong Private Key (Wrong).
4.  That `138565` was the Mainnet Chain ID because it was in `.env` (Wrong).

The user was right all along. Trust the user's data in the database, trust the `FROLODY2_KEY` string, and always remember the inverted `chain_id` rules.
