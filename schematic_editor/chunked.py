"""Chunked-коллекции для пространственного индекса."""


class _ChunkIndexBase(dict):
    """Базовый словарь с пространственным индексом по чанкам."""
    CHUNK_SIZE = 32

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._chunks = {}
        for key in self.keys():
            self._chunk_add(key)

    # --- должно быть переопределено в наследниках ---
    def _chunks_of(self, key):
        raise NotImplementedError

    # --- низкоуровневые операции с индексом ---
    def _chunk_add(self, key):
        for ck in self._chunks_of(key):
            bucket = self._chunks.get(ck)
            if bucket is None:
                bucket = self._chunks[ck] = set()
            bucket.add(key)

    def _chunk_remove(self, key):
        for ck in self._chunks_of(key):
            bucket = self._chunks.get(ck)
            if bucket is not None:
                bucket.discard(key)
                if not bucket:
                    del self._chunks[ck]

    def __setitem__(self, key, value):
        if key not in self:
            self._chunk_add(key)
        super().__setitem__(key, value)

    def __delitem__(self, key):
        if key in self:
            self._chunk_remove(key)
        super().__delitem__(key)

    def clear(self):
        super().clear()
        self._chunks.clear()

    # --- обход ключей, попадающих в чанки диапазона ---
    def _iter_chunk_keys(self, min_col, max_col, min_row, max_row):
        cs = self.CHUNK_SIZE
        for cx in range(min_col // cs, max_col // cs + 1):
            for cy in range(min_row // cs, max_row // cs + 1):
                for key in self._chunks.get((cx, cy), ()):
                    yield key


class ChunkedLayerData(_ChunkIndexBase):
    """Клетки (col, row) → item."""

    def _chunks_of(self, key):
        cs = self.CHUNK_SIZE
        return ((key[0] // cs, key[1] // cs),)

    def cells_in_view(self, min_col, max_col, min_row, max_row):
        for key in self._iter_chunk_keys(min_col, max_col, min_row, max_row):
            yield key, self[key]


class ChunkedLayerLines(_ChunkIndexBase):
    """Линии ((c1,r1),(c2,r2)) → item."""

    def _chunks_of(self, key):
        (c1, r1), (c2, r2) = key
        min_c, max_c = (c1, c2) if c1 <= c2 else (c2, c1)
        min_r, max_r = (r1, r2) if r1 <= r2 else (r2, r1)
        cs = self.CHUNK_SIZE
        return ((cx, cy)
                for cx in range(min_c // cs, max_c // cs + 1)
                for cy in range(min_r // cs, max_r // cs + 1))

    def lines_in_view(self, min_col, max_col, min_row, max_row):
        seen = set()
        for key in self._iter_chunk_keys(min_col, max_col, min_row, max_row):
            if key in seen:
                continue
            seen.add(key)
            yield key, self[key]

    def lines_at_cell(self, c, r):
        """Линии с концом в клетке (c, r) — O(размер чанка)."""
        cs = self.CHUNK_SIZE
        cell = (c, r)
        for key in self._chunks.get((c // cs, r // cs), ()):
            if key[0] == cell or key[1] == cell:
                yield key