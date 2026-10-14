"""Chunked streaming reader extracting batches with memory footprint capped below 250MB.
Strict zero em dash policy enforced.
"""
import tracemalloc
import gc
from typing import List, Dict, Any, Generator, Optional
from src.models import (
    MigrationRecord,
    MigrationBatch,
    MigrationSourceType,
    ChunkProgress
)
from src.config import DatabaseMigrationConfig
from src.source_extractor import SourceExtractor


class StreamReader(SourceExtractor):
    """Chunked streaming reader extracting batches with strict memory bounds."""

    def __init__(self, config: Optional[DatabaseMigrationConfig] = None):
        super().__init__(config)
        self.chunk_history: List[ChunkProgress] = []
        if not tracemalloc.is_tracing():
            tracemalloc.start()

    def get_current_memory_mb(self) -> float:
        """Returns current allocated memory in megabytes."""
        current, _ = tracemalloc.get_traced_memory()
        return round(current / (1024.0 * 1024.0), 2)

    def get_peak_memory_mb(self) -> float:
        """Returns peak memory tracked in megabytes."""
        _, peak = tracemalloc.get_traced_memory()
        return round(peak / (1024.0 * 1024.0), 2)

    def check_memory_cap(self) -> bool:
        """Verifies current memory stays beneath configured cap."""
        mem_mb = self.get_current_memory_mb()
        if mem_mb > self.config.max_memory_mb_cap:
            gc.collect()
            current_after, _ = tracemalloc.get_traced_memory()
            mem_after = current_after / (1024.0 * 1024.0)
            if mem_after > self.config.max_memory_mb_cap:
                raise MemoryError(
                    f"Memory ceiling exceeded: {mem_after:.2f} MB exceeds {self.config.max_memory_mb_cap} MB cap"
                )
        return True

    def stream_chunks(
        self,
        table_name: str,
        dataset: List[Dict[str, Any]],
        start_offset: int = 0,
        batch_size: Optional[int] = None
    ) -> Generator[MigrationBatch, None, None]:
        """Streams batches yielding MigrationBatch while tracking ChunkProgress and enforcing memory limits."""
        chunk_size = batch_size or self.config.batch_size
        total_rows = len(dataset)

        for batch in self.stream_records_from_dataset(table_name, dataset, start_offset, chunk_size):
            self.check_memory_cap()
            progress = ChunkProgress(
                chunk_id=batch.batch_id,
                table_name=table_name,
                start_offset=batch.start_offset,
                end_offset=batch.end_offset,
                total_records=total_rows,
                processed_records=self.total_extracted,
                memory_used_mb=self.get_current_memory_mb(),
                is_completed=(batch.end_offset >= total_rows)
            )
            self.chunk_history.append(progress)
            yield batch
