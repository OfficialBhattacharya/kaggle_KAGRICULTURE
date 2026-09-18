"""Rebuild a submission from an agent's main.py, byte-for-byte.

The competition takes a `submission.tar.gz` containing `main.py`. The submitted
notebook carries the agent as a base85+gzip payload with a SHA256 guard, and
rebuilds both artefacts on run.

Everything here is pinned so the output is deterministic: `mtime=0` on both the
tar entry and the gzip wrapper, `GNU_FORMAT`, fixed mode. Without those, two
builds of identical source produce different archive bytes and the SHA256 that
proves "this is the agent that scored 1538" stops meaning anything.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import io
import tarfile
from dataclasses import dataclass
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Artifacts:
    """The three things a packaged agent consists of."""
    source: bytes
    archive: bytes
    payload: str          # base85 of gzip(source) — what the notebook embeds

    @property
    def source_sha(self) -> str:
        return sha256(self.source)

    @property
    def archive_sha(self) -> str:
        return sha256(self.archive)

    def summary(self) -> str:
        return (f"source  {len(self.source):>9,} bytes  sha256 {self.source_sha}\n"
                f"archive {len(self.archive):>9,} bytes  sha256 {self.archive_sha}\n"
                f"payload {len(self.payload):>9,} chars")


def build_archive(source: bytes) -> bytes:
    """gzip(tar(main.py)) with every timestamp zeroed, so it is reproducible."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.GNU_FORMAT) as tar:
        info = tarfile.TarInfo("main.py")
        info.size, info.mtime, info.mode = len(source), 0, 0o644
        tar.addfile(info, io.BytesIO(source))
    return gzip.compress(buf.getvalue(), mtime=0)


def build_payload(source: bytes) -> str:
    """The notebook-embeddable form. Inverse of `decode_payload`."""
    return base64.b85encode(gzip.compress(source, mtime=0)).decode()


def decode_payload(payload: str) -> bytes:
    """Recover agent source from a notebook payload. Decodes only — never execs."""
    return gzip.decompress(base64.b85decode(payload))


def package(main_py: Path, expect_source_sha: str | None = None) -> Artifacts:
    """Package an agent, optionally asserting it is the exact recorded bytes."""
    source = Path(main_py).read_bytes()
    got = sha256(source)
    if expect_source_sha and got != expect_source_sha:
        raise ValueError(
            f"source SHA mismatch for {main_py}\n  expected {expect_source_sha}\n"
            f"  got      {got}\nThe agent bytes differ from the recorded submission.")
    compile(source, str(main_py), "exec")   # syntax check; does not run the agent
    return Artifacts(source=source, archive=build_archive(source),
                     payload=build_payload(source))


def write(artifacts: Artifacts, out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"main.py": out_dir / "main.py",
             "submission.tar.gz": out_dir / "submission.tar.gz"}
    paths["main.py"].write_bytes(artifacts.source)
    paths["submission.tar.gz"].write_bytes(artifacts.archive)
    return paths
