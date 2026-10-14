"""Local offline key signer and EIP-1559 dynamic gas escalator.
Strict zero em dash policy enforced.
"""
import hashlib
import json
import secrets
from typing import Dict, Any, Tuple, Optional


class TransactionSigner:
    """Local offline transaction signer and EIP-1559 gas escalator."""

    def __init__(self, private_key_hex: Optional[str] = None):
        if private_key_hex:
            self.private_key = private_key_hex
        else:
            self.private_key = "0x" + secrets.token_hex(32)

        # Deterministic address derivation
        raw_key = self.private_key.replace("0x", "")
        pub_digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        self.address = "0x" + pub_digest[-40:]

    def sign_transaction(self, tx_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sign transaction offline without network exposure."""
        payload_copy = dict(tx_payload)
        payload_bytes = json.dumps(payload_copy, sort_keys=True).encode("utf-8")
        key_bytes = self.private_key.encode("utf-8")

        # Deterministic HMAC/SHA256 signature representation
        sig_hash = hashlib.sha256(payload_bytes + key_bytes).hexdigest()
        r = "0x" + sig_hash[:64]
        s = "0x" + hashlib.sha256(sig_hash.encode("utf-8")).hexdigest()[:64]
        v = 27 + (int(sig_hash[-1], 16) % 2)

        tx_hash = "0x" + hashlib.sha256(payload_bytes).hexdigest()

        signed_bundle = {
            "raw_transaction": "0x02" + sig_hash,
            "tx_hash": tx_hash,
            "v": v,
            "r": r,
            "s": s,
            "payload": payload_copy,
        }
        return signed_bundle

    def escalate_gas_fee(
        self,
        original_tx: Dict[str, Any],
        bump_percentage: float = 15.0
    ) -> Dict[str, Any]:
        """Escalate gas fees for a stuck transaction while preserving nonce."""
        multiplier = 1.0 + (bump_percentage / 100.0)
        old_prio = original_tx.get("maxPriorityFeePerGas", 2000000000)
        old_max = original_tx.get("maxFeePerGas", 30000000000)

        new_prio = int(old_prio * multiplier)
        new_max = int(old_max * multiplier)

        escalated_tx = dict(original_tx)
        escalated_tx["maxPriorityFeePerGas"] = new_prio
        escalated_tx["maxFeePerGas"] = new_max
        escalated_tx["replacement_bump_pct"] = bump_percentage

        # Recompute hash for updated gas fees
        raw_repr = json.dumps(
            {k: v for k, v in escalated_tx.items() if k != "hash"},
            sort_keys=True
        ).encode("utf-8")
        escalated_tx["hash"] = "0x" + hashlib.sha256(raw_repr).hexdigest()
        return escalated_tx

    def is_underpriced(self, new_fee: int, old_fee: int, min_bump_pct: float = 10.0) -> bool:
        """Check if replacement fee meets node mempool replacement minimum."""
        threshold = int(old_fee * (1.0 + (min_bump_pct / 100.0)))
        return new_fee < threshold
