from enum import StrEnum
from os import PathLike

from pyvips.enums import Access, FailOn, ForeignSubsample

_StrPath = str | PathLike[str]

class Interpretation(StrEnum):
    ERROR = "error"
    MULTIBAND = "multiband"
    B_W = "b-w"
    HISTOGRAM = "histogram"
    XYZ = "xyz"
    LAB = "lab"
    CMYK = "cmyk"
    LABQ = "labq"
    RGB = "rgb"
    CMC = "cmc"
    LCH = "lch"
    LABS = "labs"
    SRGB = "srgb"
    YXY = "yxy"
    FOURIER = "fourier"
    RGB16 = "rgb16"
    GREY16 = "grey16"
    MATRIX = "matrix"
    SCRGB = "scrgb"
    HSV = "hsv"

class BandFormat(StrEnum):
    NOTSET = "notset"
    UCHAR = "uchar"
    CHAR = "char"
    USHORT = "ushort"
    SHORT = "short"
    UINT = "uint"
    INT = "int"
    FLOAT = "float"
    COMPLEX = "complex"
    DOUBLE = "double"
    DPCOMPLEX = "dpcomplex"

class Kernel(StrEnum):
    NEAREST = "nearest"
    LINEAR = "linear"
    CUBIC = "cubic"
    MITCHELL = "mitchell"
    LANCZOS2 = "lanczos2"
    LANCZOS3 = "lanczos3"

class Extend(StrEnum):
    BLACK = "black"
    COPY = "copy"
    REPEAT = "repeat"
    MIRROR = "mirror"
    WHITE = "white"
    BACKGROUND = "background"

class ForeignWebpPreset(StrEnum):
    DEFAULT = "default"
    PICTURE = "picture"
    PHOTO = "photo"
    DRAWING = "drawing"
    ICON = "icon"
    TEXT = "text"

class Image:
    # I/O
    @staticmethod
    def new_from_file(vips_filename: _StrPath, **kwargs) -> Image: ...

    # Basic information
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    @property
    def bands(self) -> int: ...
    @property
    def format(self) -> BandFormat: ...
    @property
    def interpretation(self) -> Interpretation: ...

    # Transform
    def crop(self, left: int, top: int, width: int, height: int) -> Image: ...
    def resize(
        self,
        scale: float,
        /,
        *,
        kernel: str | Kernel = ...,
        gap: float = ...,
        vscale: float | None = ...,
    ) -> Image: ...
    def embed(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        /,
        *,
        extend: str | Extend = ...,
        background: list[float] = ...,
    ) -> Image: ...
    def addalpha(self) -> Image: ...

    # File I/O
    def write_to_file(self, filename: _StrPath, **kwargs) -> Image: ...
    def webpsave(
        self,
        filename: _StrPath,
        *,
        Q: int = ...,
        lossless: bool = ...,
        preset: str | ForeignWebpPreset = ...,
        smart_subsample: bool = ...,
        near_lossless: bool = ...,
        alpha_q: int = ...,
        min_size: bool = ...,
        kmin: int = ...,
        kmax: int = ...,
        effort: int = ...,
        profile: str = ...,
        mixed: bool = ...,
        strip: bool = ...,
        background: list[float] = ...,
        page_height: int = ...,
    ): ...
    def jxlsave(
        self,
        filename: _StrPath,
        *,
        tier: int = ...,
        distance: float = ...,
        effort: int = ...,
        lossless: bool = ...,
        Q: int = ...,
        strip: bool = ...,
        background: list[float] = ...,
        page_height: int = ...,
    ): ...

    # Buffer I/O
    def write_to_buffer(self, format_string: str, **kwargs) -> bytes: ...
    @staticmethod
    def jpegload_buffer(
        buffer: bytes,
        shrink: int = ...,
        autorotate: bool = ...,
        memory: bool = ...,
        access: str | Access = ...,
        fail_on: str | FailOn = ...,
        flags: bool = ...,
    ) -> Image: ...
    def jpegsave_buffer(
        self,
        Q: int = ...,
        profile: str = ...,
        optimize_coding: bool = ...,
        interlace: bool = ...,
        trellis_quant: bool = ...,
        overshoot_deringing: bool = ...,
        optimize_scans: bool = ...,
        quant_table: int = ...,
        subsample_mode: str | ForeignSubsample = ...,
        restart_interval: int = ...,
        strip: bool = ...,
        background: list[float] = ...,
        page_height: int = ...,
    ) -> bytes: ...
    def pngsave_buffer(
        self,
        compression: int = ...,
        interlace: bool = ...,
        profile: str = ...,
        filter: int = ...,
        palette: bool = ...,
        Q: int = ...,
        dither: float = ...,
        bitdepth: int = ...,
        effort: int = ...,
        strip: bool = ...,
        background: list[float] = ...,
        page_height: int = ...,
    ) -> bytes: ...
