# This file is part of https://github.com/KurtBoehm/periplus.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os
from collections.abc import Buffer, Iterator
from io import RawIOBase
from pathlib import Path
from typing import BinaryIO, final, override
from zipfile import ZipFile, ZipInfo


@final
class OtfStream(RawIOBase):
    """In-memory write-only stream that exposes written data in chunks."""

    def __init__(self) -> None:
        """Initialize the stream with an empty internal buffer."""
        # Accumulated bytes written to the stream.
        self._buffer = b""

    @override
    def writable(self) -> bool:
        """
        Indicate that the stream supports writing.

        :return: ``True`` since this is a write-only stream.
        """
        return True

    @override
    def write(self, b: Buffer) -> int:
        """
        Append bytes to the internal buffer.

        :param b: Bytes to write.
        :return: Number of bytes written.
        """
        len_before = len(self._buffer)
        self._buffer += b
        return len(self._buffer) - len_before

    def get(self) -> bytes:
        """
        Return and clear the current buffer contents.

        :return: Bytes written since the last call to :meth:`get`.
        """
        chunk = self._buffer
        self._buffer = b""
        return chunk


def generate_zip(
    fp: Path,
    *,
    paths: list[Path] | None = None,
    chunk_size: int = 0x8000,
) -> Iterator[bytes]:
    """
    Lazily generate a ZIP archive as byte chunks.

    Files under ``paths`` (or ``fp`` if ``paths`` is ``None``) are added to a ZIP file
    whose internal paths are relative to ``fp``. The ZIP data is yielded incrementally
    as it is written.

    :param fp: Root path used for relative paths inside the archive.
    :param paths: Optional list of files/directories to include. If omitted,
                  only ``fp`` is included.
    :param chunk_size: Size of file read chunks in bytes.
    :yield: Consecutive chunks of ZIP file bytes.
    """
    if paths is None:
        # Default to archiving only fp.
        paths = [fp]

    # Flatten list of paths; if a path is a directory, walk it recursively.
    paths = [
        pi
        for p in paths
        for pi in (
            (Path(root) / file for root, _, files in os.walk(p) for file in files)
            if p.is_dir()
            else (p,)
        )
    ]

    # In-memory streaming sink for ZIP.
    with OtfStream() as stream:
        # Create archive on top of OtfStream.
        with ZipFile(stream, "w") as zf:
            for path in paths:
                # Build ZipInfo with arcname relative to root fp.
                z_info = ZipInfo.from_file(path, path.relative_to(fp))
                # Stream file contents into ZIP entry.
                with open(path, "rb") as e, zf.open(z_info, "w") as d:
                    for chunk in iter(lambda: e.read(chunk_size), b""):
                        d.write(chunk)
                        # Yield zip bytes produced so far.
                        yield stream.get()
        # Flush any remaining bytes after closing the archive.
        yield stream.get()


@final
class ZipIO(BinaryIO):
    """
    File-like binary reader that streams a ZIP archive on the fly.

    Wraps :func:`generate_zip` and exposes a standard :meth:`read` interface to consume
    the generated ZIP bytes.
    """

    def __init__(
        self,
        fp: Path,
        *,
        paths: list[Path] | None = None,
        chunk_size: int = 0x8000,
    ) -> None:
        """
        Initialize the streaming ZIP reader.

        :param fp: Root path used for relative paths inside the archive.
        :param paths: Optional list of files/directories to include.
        :param chunk_size: Size of file read chunks in bytes.
        """
        # ZIP generator.
        self.gen = generate_zip(fp, paths=paths, chunk_size=chunk_size)
        # Initial buffer chunk.
        self.buf = next(self.gen, None)

    @override
    def read(self, n: int = -1, /) -> bytes:
        """
        Read up to ``n`` bytes from the generated ZIP stream.

        If ``n`` is ``-1``, all remaining data is read until EOF.

        :param n: Maximum number of bytes to read, or ``-1`` for all remaining.
        :return: Bytes read from the ZIP stream (may be fewer than ``n`` at EOF).
        """
        buf = self.buf
        if buf is None:
            # Already exhausted.
            return b""

        if n == -1:
            # Read all remaining chunks and concatenate.
            while (b := next(self.gen, None)) is not None:
                buf += b
            return buf

        # Ensure buffer has at least n bytes or we’ve exhausted generator.
        while len(buf) < n and (b := next(self.gen, None)) is not None:
            buf += b

        # Keep leftover bytes for next read.
        self.buf = buf[n:]
        return buf[:n]
