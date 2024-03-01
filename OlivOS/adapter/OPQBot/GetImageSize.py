#!/usr/bin/env python3

from io import BytesIO
from typing import Union, Dict, NamedTuple, IO
from os import fstat, walk
from os.path import isdir, join as join_path
from struct import unpack
from enum import Enum
from os import PathLike

__all__ = 'ImInfo', 'ImError', 'ImFormat', 'get_image_size', 'get_image_size_from_path', 'get_image_size_from_reader'

# Original source: https://stackoverflow.com/questions/15800704/get-image-size-without-loading-image-into-memory
#-------------------------------------------------------------------------------
# Name:        get_image_size
# Purpose:     extract image dimensions given a file path using just
#              core modules
#
# Author:      Paulo Scardine, Mathias Panzenböck (based on code from Emmanuel VAÏSSE)
#
# Created:     26/09/2013
# Copyright:   (c) Paulo Scardine 2013, (c) Mathias Panzenböck 2022
# Licence:     MIT
#-------------------------------------------------------------------------------

TIFF_TYPES = [
    (1, "B"),  #  1 BYTE
    (1, "c"),  #  2 ASCII
    (2, "H"),  #  3 SHORT
    (4, "L"),  #  4 LONG
    (8, "LL"), #  5 RATIONAL
    (1, "b"),  #  6 SBYTE
    (1, "c"),  #  7 UNDEFINED
    (2, "h"),  #  8 SSHORT
    (4, "l"),  #  9 SLONG
    (8, "ll"), # 10 SRATIONAL
    (4, "f"),  # 11 FLOAT
    (8, "d")   # 12 DOUBLE
]

TIFF_TYPES_BE = [(sz, '>' + fmt) for sz, fmt in TIFF_TYPES]
TIFF_TYPES_LE = [(sz, '<' + fmt) for sz, fmt in TIFF_TYPES]

class ImFormat(Enum):
    GIF     =  1
    PNG     =  2
    BMP     =  3
    JPEG    =  4
    WEBP    =  5
    QOI     =  6
    PSD     =  7
    XCF     =  8
    ICO     =  9
    AVIF    = 10
    TIFF    = 11
    OpenEXR = 12
    PCX     = 13
    TGA     = 14
    DDS     = 15
    HEIF    = 16
    JP2K    = 17
    DIB     = 18
    VTF     = 19

    def __str__(self) -> str:
        return FORMAT_NAMES[self]

FORMAT_NAMES: Dict[ImFormat, str] = {
    ImFormat.GIF    : 'GIF',
    ImFormat.PNG    : 'PNG',
    ImFormat.BMP    : 'BMP',
    ImFormat.JPEG   : 'JPEG',
    ImFormat.WEBP   : 'WebP',
    ImFormat.QOI    : 'QOI',
    ImFormat.PSD    : 'PSD',
    ImFormat.XCF    : 'XCF',
    ImFormat.ICO    : 'ICO',
    ImFormat.AVIF   : 'AVIF',
    ImFormat.TIFF   : 'TIFF',
    ImFormat.OpenEXR: 'OpenEXR',
    ImFormat.PCX    : 'PCX',
    ImFormat.TGA    : 'TGA',
    ImFormat.DDS    : 'DDS',
    ImFormat.HEIF   : 'HEIF',
    ImFormat.JP2K   : 'JPEG 2000',
    ImFormat.DIB    : 'DIB',
    ImFormat.VTF    : 'VTF',
}

class ImError(Exception):
    __slots__ = ()

class ParserError(ImError):
    __slots__ = 'format',
    format: ImFormat

    def __init__(self, format: ImFormat) -> None:
        super().__init__()
        self.format = format

    def __str__(self) -> str:
        return f"Parser Error {self.format}"

class UnsupportedFormat(ImError):
    __slots__ = ()

    def __str__(self) -> str:
        return "Unsupported Format"

def is_tga(file: IO[bytes]) -> bool:
    file.seek(-18, 2)
    sig = file.read(18)
    return sig == b"TRUEVISION-XFILE.\0"

class ImInfo(NamedTuple):
    width:  int
    height: int
    format: ImFormat

def find_riff_chunk(file: IO[bytes], name: bytes, chunk_size: int, format: ImFormat) -> int:
    sub_chunk_size: int
    offset = 0

    while True:
        if offset > chunk_size:
            raise ParserError(format)

        buf = file.read(8)
        sub_chunk_size, = unpack(">I", buf[:4])

        if sub_chunk_size < 8:
            raise ParserError(format)

        if buf[4:] == name:
            break

        offset += sub_chunk_size
        file.seek(sub_chunk_size - 8, 1)

    return sub_chunk_size

def get_image_size_from_path(file_path: Union[str, PathLike]) -> ImInfo:
    with open(file_path, 'rb') as input:
        return get_image_size_from_reader(input)

def get_image_size_from_buffer(buffer: Union[bytes, bytearray, memoryview]) -> ImInfo:
    return get_image_size_from_reader(BytesIO(buffer))

def get_image_size(input: Union[str, PathLike, bytes, bytearray, memoryview, IO[bytes]]) -> ImInfo:
    if isinstance(input, (bytes, bytearray, memoryview)):
        return get_image_size_from_buffer(input)

    if isinstance(input, (str, PathLike)):
        return get_image_size_from_path(input)

    return get_image_size_from_reader(input)

def get_image_size_from_reader(input: IO[bytes]) -> ImInfo:
    """
    Return (width, height, format) for a given image file content.
    input must be seekable. May raise ImError.
    """

    data = input.read(30)
    if isinstance(input, BytesIO):
        size = len(input.getbuffer())
    else:
        meta = fstat(input.fileno())
        size = meta.st_size

    if size >= 10 and (data.startswith(b'GIF87a') or data.startswith(b'GIF89a')):
        # GIFs
        width, height = unpack("<HH", data[6:10])
        return ImInfo(width, height, ImFormat.GIF)
    elif data.startswith(b'\x89PNG\r\n\x1a\n'):
        # PNG
        if size < 24:
            raise ParserError(ImFormat.PNG)

        chunk_size, = unpack(">L", data[8:12])
        if chunk_size < 0 or data[12:16] != b'IHDR':
            raise ParserError(ImFormat.PNG)

        width, height = unpack(">LL", data[16:24])
        return ImInfo(width, height, ImFormat.PNG)
    elif size >= 7 and data.startswith(b"\xff\xd8"):
        # JPEG
        input.seek(3)
        b = data[2:3]
        try:
            while b and b != b'\xDA':
                while b != b'\xFF':
                    b = input.read(1)
                    if not b:
                        raise ParserError(ImFormat.JPEG)
                while b == b'\xFF':
                    b = input.read(1)
                    if not b:
                        raise ParserError(ImFormat.JPEG)
                b0 = b[0]
                if b0 >= 0xC0 and b0 <= 0xC3:
                    input.seek(3, 1)
                    height, width = unpack(">HH", input.read(4))
                    return ImInfo(width, height, ImFormat.JPEG)
                else:
                    input.seek(unpack(">H", input.read(2))[0] - 2, 1)
                b = input.read(1)

            raise ParserError(ImFormat.JPEG)
        except Exception as error:
            raise ParserError(ImFormat.JPEG) from error
    elif data.startswith(b'RIFF') and size >= 30 and data[8:12] == b'WEBP':
        # WEBP
        # learned format from: https://wiki.tcl-lang.org/page/Reading+WEBP+image+dimensions
        hdr = data[12:16]
        if hdr == b'VP8L':
            b0 = data[21]
            b1 = data[22]
            b2 = data[23]
            b3 = data[24]
            width  = 1 + (((b1 & 0x3F) << 8) | b0)
            height = 1 + (((b3 & 0xF) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
        elif hdr == b'VP8 ':
            b0 = data[23]
            b1 = data[24]
            b2 = data[25]
            if b0 != 0x9d or b1 != 0x01 or b2 != 0x2a:
                raise ParserError(ImFormat.WEBP)
            w, h = unpack("<HH", data[26:30])
            width  = w & 0x3ffff
            height = h & 0x3ffff
        elif hdr == b'VP8X':
            w1 = data[24]
            w2 = data[25]
            w3 = data[26]
            h1 = data[27]
            h2 = data[28]
            h3 = data[29]

            width  = (w1 | w2 << 8 | w3 << 16) + 1
            height = (h1 | h2 << 8 | h3 << 16) + 1
        else:
            raise ParserError(ImFormat.WEBP)

        return ImInfo(width, height, ImFormat.WEBP)
    elif data[4:12] in (b'ftypavif', b'ftypheic'):
        # AVIF and HEIF
        ftype_size, = unpack(">I", data[0:4])
        input.seek(ftype_size)

        format = ImFormat.AVIF if data[8:12] == b'avif' else ImFormat.HEIF

        # chunk nesting: meta > iprp > ipco > ispe
        # search meta chunk
        chunk_size = find_riff_chunk(input, b"meta", 0xFFFF_FFFF_FFFF_FFFF, format)
        if chunk_size < 12:
            raise ParserError(format)

        input.seek(4, 1)
        chunk_size = find_riff_chunk(input, b"iprp", chunk_size - 12, format)
        chunk_size = find_riff_chunk(input, b"ipco", chunk_size -  8, format)
        chunk_size = find_riff_chunk(input, b"ispe", chunk_size -  8, format)

        if chunk_size < 12:
            raise ParserError(format)

        data = input.read(12)
        if len(data) < 12:
            raise ParserError(format)
        width, height = unpack(">II", data[4:])
        return ImInfo(width, height, format)
    elif size >= 24 and data.startswith(b"\0\0\0\x0CjP  ") and data[16:24] == b"ftypjp2 ":
        # JPEG 2000
        chunk_size, = unpack(">I", data[12:16])
        input.seek(12 + chunk_size)

        chunk_size = find_riff_chunk(input, b"jp2h", 0xFFFF_FFFF_FFFF_FFFF, ImFormat.JP2K)
        chunk_size = find_riff_chunk(input, b"ihdr", chunk_size, ImFormat.JP2K)

        if chunk_size < 8:
            raise ParserError(ImFormat.JP2K)

        data = input.read(8)
        if len(data) < 8:
            raise ParserError(ImFormat.JP2K)

        height, width = unpack(">II", data)
        return ImInfo(width, height, ImFormat.JP2K)
    elif data.startswith(b'BM') and data[6:10] == b'\0\0\0\0':
        # BMP
        file_size, = unpack("<I", data[2:6])
        min_size = min(file_size, size)
        if min_size < 22:
            raise ParserError(ImFormat.BMP)

        header_size, = unpack("<I", data[14:18])
        if header_size == 12:
            width, height = unpack("<hh", data[18:24])
        else:
            if min_size < 26 or header_size <= 12:
                raise ParserError(ImFormat.BMP)
            width, height = unpack("<ii", data[18:26])
        # height is negative when stored upside down
        return ImInfo(width, abs(height), ImFormat.BMP)
    elif size >= 8 and (data.startswith(b"II\052\000") or data.startswith(b"MM\000\052")):
        # from here: https://github.com/scardine/image_size
        # Standard TIFF, big- or little-endian
        # BigTIFF and other different but TIFF-like formats are not
        # supported currently
        byteOrder = data[:2]
        # maps TIFF type id to size (in bytes)
        # and python format char for struct
        if byteOrder == b"MM":
            tiffTypes = TIFF_TYPES_BE
            ulong  = ">L"
            ushort = ">H"
        else:
            tiffTypes = TIFF_TYPES_LE
            ulong  = "<L"
            ushort = "<H"
        ifdOffset = unpack(ulong, data[4:8])[0]
        try:
            countSize = 2
            input.seek(ifdOffset)
            ec = input.read(countSize)
            ifdEntryCount = unpack(ushort, ec)[0]
            # 2 bytes: TagId + 2 bytes: type + 4 bytes: count of values + 4
            # bytes: value offset
            ifdEntrySize = 12
            width  = -1
            height = -1
            for i in range(ifdEntryCount):
                entryOffset = ifdOffset + countSize + i * ifdEntrySize
                input.seek(entryOffset)
                btag = input.read(2)
                tag = unpack(ushort, btag)[0]
                if tag == 256 or tag == 257:
                    # if type indicates that value fits into 4 bytes, value
                    # offset is not an offset but value itself
                    btype = input.read(2)
                    ftype = unpack(ushort, btype)[0]
                    if ftype < 1 or ftype > len(tiffTypes):
                        raise ParserError(ImFormat.TIFF)
                    typeSize, typeChar = tiffTypes[ftype - 1]
                    input.seek(entryOffset + 8)
                    bvalue = input.read(typeSize)
                    if ftype == 5 or ftype == 10:
                        # rational
                        a, b = unpack(typeChar, bvalue)[0]
                        value = int(a) // int(b)
                    else:
                        value = int(unpack(typeChar, bvalue)[0])

                    if value < 0:
                        value = 0

                    if tag == 256:
                        width  = value
                    else:
                        height = value
                    if width > -1 and height > -1:
                        return ImInfo(width, height, ImFormat.TIFF)

            raise ParserError(ImFormat.TIFF)
        except Exception as error:
            raise ParserError(ImFormat.TIFF) from error
    elif data.startswith(b'qoif') and size >= 14:
        # QOI
        width, height = unpack(">II", data[4:12])
        return ImInfo(width, height, ImFormat.QOI)
    elif data.startswith(b'8BPS\0\x01\0\0\0\0\0\0') and size >= 22:
        # PSD
        height, width = unpack(">II", data[14:22])
        return ImInfo(width, height, ImFormat.PSD)
    elif data.startswith(b'gimp xcf ') and size >= 22 and data[13] == 0:
        # XCF
        width, height = unpack(">II", data[14:22])
        return ImInfo(width, height, ImFormat.XCF)
    elif data.startswith(b'\0\0\x01\0') and size >= 6:
        # ICO
        count, = unpack("<H", data[4:6])
        input.seek(6)
        width  = 0
        height = 0
        for _ in range(count):
            data = input.read(16)
            if len(data) < 16:
                raise ParserError(ImFormat.ICO)
            w = data[0]
            h = data[1]
            if w >= width and h >= height:
                width  = w
                height = h
        return ImInfo(width, height, ImFormat.ICO)
    elif data.startswith(b"\x76\x2f\x31\x01") and size > 8 and (data[4] == 0x01 or data[4] == 0x02):
        # OpenEXR
        # https://www.openexr.com/documentation/openexrfilelayout.pdf
        input.seek(8)
        while True:
            name_buf = bytearray()
            while True:
                chunk = input.read(1)
                if not chunk:
                    raise ParserError(ImFormat.OpenEXR)
                byte = chunk[0]
                if byte == 0:
                    break
                name_buf.append(byte)

            if len(name_buf) == 0:
                break

            type_buf = bytearray()
            while True:
                chunk = input.read(1)
                if not chunk:
                    raise ParserError(ImFormat.OpenEXR)
                byte = chunk[0]
                if byte == 0:
                    break
                type_buf.append(byte)

            size_buf = input.read(4)
            if len(size_buf) < 4:
                raise ParserError(ImFormat.OpenEXR)
            size, = unpack("<I", size_buf)

            if name_buf == b"displayWindow":
                if type_buf != b"box2i" or size != 16:
                    raise ParserError(ImFormat.OpenEXR)

                box_buf = input.read(16)
                x1, y1, x2, y2 = unpack("<iiii", box_buf)
                width  = x2 - x1 + 1
                height = y2 - y1 + 1
                if width <= 0 or height <= 0:
                    raise ParserError(ImFormat.OpenEXR)
                return ImInfo(width, height, ImFormat.OpenEXR)
            else:
                input.seek(size, 1)
        raise ParserError(ImFormat.OpenEXR)
    elif size >= 30 and data[0] == 0x0A and data[1] < 6 and data[2] < 2 and data[3] in (1, 2, 4, 8):
        # PCX
        x1, y1, x2, y2 = unpack("<HHHH", data[4:12])
        width  = x2 - x1 + 1
        height = y2 - y1 + 1
        if width <= 0 or height <= 0:
            raise ParserError(ImFormat.PCX)
        return ImInfo(width, height, ImFormat.PCX)
    elif size >= 20 and data.startswith(b"DDS \x7C\0\0\0") and unpack("<I", data[8:12])[0] & 0x1007:
        # DDS
        # http://doc.51windows.net/directx9_sdk/graphics/reference/DDSFileReference/ddsfileformat.htm
        # https://docs.microsoft.com/en-us/windows/win32/direct3ddds/dds-header
        height, width = unpack("<II", data[12:20])
        return ImInfo(width, height, ImFormat.DDS)
    elif size >= 14 and data.startswith(b"\x28\0\0\0") and data[12:14] == b"\x01\0" and data[15] == 0:
        # DIB
        width, height = unpack("<ii", data[4:12])
        return ImInfo(width, abs(height), ImFormat.DIB)
    elif size >= 20 and data.startswith(b'VTF\0'):
        # VTF
        header_size, width, height = unpack("<IHH", data[12:20])
        if header_size < 20:
            raise ParserError(ImFormat.VTF)
        return ImInfo(width, height, ImFormat.VTF)
    elif size >= 30 and data[1] < 2 and data[2] < 12 and is_tga(input):
        # TGA
        width, height = unpack("<HH", data[12:16])
        return ImInfo(width, height, ImFormat.TGA)

    raise UnsupportedFormat()