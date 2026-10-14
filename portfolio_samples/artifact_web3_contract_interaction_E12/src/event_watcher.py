"""Contract event log filter with block range chunking and reorg confirmation gates.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Tuple


class ContractEventWatcher:
    """Manages block range chunking and reorg-depth event finality."""

    def __init__(self, reorg_depth: int = 12):
        self.reorg_depth = reorg_depth
        self.finalized_events: List[Dict[str, Any]] = []
        self.unfinalized_events: List[Dict[str, Any]] = []

    def chunk_block_range(self, from_block: int, to_block: int, chunk_size: int = 2000) -> List[Tuple[int, int]]:
        """Break down broad block queries into bounded ranges."""
        chunks: List[Tuple[int, int]] = []
        curr = from_block
        while curr <= to_block:
            end = min(curr + chunk_size - 1, to_block)
            chunks.append((curr, end))
            curr = end + 1
        return chunks

    def process_incoming_events(self, raw_events: List[Dict[str, Any]], current_head_block: int) -> Tuple[int, int]:
        """Filter events into finalized vs unfinalized based on reorg safety depth."""
        finalized_count = 0
        unfinalized_count = 0

        for ev in raw_events:
            ev_block = ev.get("block_number", 0)
            confirmations = current_head_block - ev_block
            if confirmations >= self.reorg_depth:
                ev["status"] = "FINALIZED"
                ev["confirmations"] = confirmations
                self.finalized_events.append(ev)
                finalized_count += 1
            else:
                ev["status"] = "UNFINALIZED"
                ev["confirmations"] = confirmations
                self.unfinalized_events.append(ev)
                unfinalized_count += 1

        return finalized_count, unfinalized_count
