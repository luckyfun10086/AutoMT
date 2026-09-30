# -*- coding: utf-8 -*-
"""Kirikiri XP3 封包读取/写入（纯 Python、零依赖）
==================================================
布局（与 GARbro ArcXP3.cs 一致，已在真实档案上验证）：
  头: 11 字节 magic "XP3\\r\\n \\n\\x1a\\x8b\\x67\\x01" + u64 索引偏移
      索引处 u32 flag & 0x80 → 二级索引：u64 @ +9 为真实索引偏移
  索引头: u8 type(0=raw 1=zlib) + u64 zsize + u64 usize + 数据
  索引体: 若干 chunk: 4 字节 tag + u64 size + 载荷
      'File' 载荷内含子 chunk（同样 tag+u64 头）：
        'info': u32 protect + u64 original_size + u64 archived_size
                + u32 名长(字节,UTF-16LE)（无 offset 字段，实测布局）
        'segm': 每段 28 字节: u32 flag(0=raw 1=zlib 2=加密) + u64 offset
                + u64 original_size + u64 archived_size
        'adlr': u32 adler32
        'time': u64 修改时间
  数据区: 段数据直接位于 segm.offset（无内联段表，GARbro 同款读法）

写入策略（非破坏性）：
  不改动原档案，生成 patch 封包（Kirikiri 按文件名序后挂载者覆盖先者）——
  卸载汉化只需删除 patch 文件，原游戏零风险。
"""
import struct, zlib

MAGIC = b"XP3\r\n \n\x1a\x8b\x67\x01"


class Entry:
    __slots__ = ("name", "protect", "offset", "archived_size", "original_size",
                 "segments", "adler", "mtime")
    def __init__(self):
        self.name = ""
        self.protect = 0
        self.offset = 0
        self.archived_size = 0
        self.original_size = 0
        self.segments = []     # (flag, offset, original_size, archived_size)
        self.adler = 0
        self.mtime = 0

    def __repr__(self):
        return f"<Entry {self.name!r} {self.original_size}B seg={len(self.segments)}>"


def _read_chunk_header(f):
    tag = f.read(4)
    if len(tag) < 4:
        return None, None
    size = struct.unpack("<Q", f.read(8))[0]
    return tag, size


def parse_index(f):
    """解析 XP3 索引 → [Entry]。f 为已打开的二进制文件对象。"""
    if f.read(11) != MAGIC:
        raise ValueError("不是 XP3 档案（magic 不符）")
    idx = struct.unpack("<Q", f.read(8))[0]
    f.seek(idx)
    flag = struct.unpack("<I", f.read(4))[0]
    if flag & 0x80:                      # 二级索引（v2 归档器写入的间接指针）
        f.seek(idx + 9)
        idx = struct.unpack("<Q", f.read(8))[0]
        f.seek(idx)
    htype = struct.unpack("<B", f.read(1))[0]
    if htype == 1:
        zsize = struct.unpack("<Q", f.read(8))[0]
        usize = struct.unpack("<Q", f.read(8))[0]
        data = zlib.decompress(f.read(zsize))
        if usize and len(data) != usize:
            raise ValueError(f"索引解压尺寸不符 {len(data)} != {usize}")
    elif htype == 0:
        data = f.read()
    else:
        raise ValueError(f"未知索引类型 {htype}")

    entries = []
    pos = 0
    while pos + 12 <= len(data):
        tag = data[pos:pos + 4]
        size = struct.unpack_from("<Q", data, pos + 4)[0]
        body = data[pos + 12:pos + 12 + size]
        pos += 12 + size
        if tag == b"File":
            e = _parse_file_chunk(body)
            if e is not None:
                entries.append(e)
    return entries


def _parse_file_chunk(body):
    e = Entry()
    pos = 0
    while pos + 12 <= len(body):
        tag = body[pos:pos + 4]
        size = struct.unpack_from("<Q", body, pos + 4)[0]
        sub = body[pos + 12:pos + 12 + size]
        pos += 12 + size
        if tag == b"info":
            # 实测布局: protect + original + archived + 名字(UTF-16LE 直到块尾)
            # 兼容变体: 少数归档器带 u32 名长前缀（长度恰好吻合时启用）
            (e.protect, e.original_size, e.archived_size) = \
                struct.unpack_from("<IQQ", sub, 0)
            if len(sub) >= 24:
                nl = struct.unpack_from("<I", sub, 20)[0]
                if 24 + nl == len(sub):
                    e.name = sub[24:].decode("utf-16-le", "replace")
                else:
                    e.name = sub[20:].decode("utf-16-le", "replace")
            else:
                e.name = sub[20:].decode("utf-16-le", "replace")
        elif tag == b"segm":
            for i in range(0, size // 28):
                e.segments.append(struct.unpack_from("<IQQQ", sub, i * 28))
        elif tag == b"adlr":
            e.adler = struct.unpack_from("<I", sub, 0)[0]
        elif tag == b"time":
            e.mtime = struct.unpack_from("<Q", sub, 0)[0]
    if e.segments:
        e.offset = e.segments[0][1]
    return e if e.name else None


def read_entry_data(f, e):
    """读取条目全部数据（拼接段，zlib 解压）。"""
    out = bytearray()
    for flag, off, orig, arch in e.segments:
        f.seek(off)
        raw = f.read(arch)
        if flag == 1:
            out += zlib.decompress(raw)
        elif flag == 0:
            out += raw
        else:
            raise ValueError(f"{e.name}: 段加密 flag={flag}（自定义加密，暂不支持）")
    return bytes(out)


# ---------------------------------------------------------------- 写入
def write_xp3(f, files, compress=True):
    """files: [(内部路径, bytes, mtime_ms)] → 写出 XP3 档案到 f（布局与实测一致）。
    data 以 40 字节头部占位开头 → len(data) 即文件内绝对偏移。"""
    header_len = 0x28          # 与主流归档器相同：数据区从 0x28 起
    data = bytearray(b"\x00" * header_len)
    placed = []      # (name_bytes, data_offset, flag, archived, original, mtime)

    for name, content, mtime in files:
        off = len(data)                       # 绝对偏移（含头部占位）
        nb = name.encode("utf-16-le")
        raw = zlib.compress(content, 6) if compress else content
        flag = 1 if compress else 0
        data += raw
        placed.append((nb, off, flag, len(raw), len(content), mtime))

    index = bytearray()
    import zlib as _z
    for nb, off, flag, arch, orig, mtime in placed:
        file_body = bytearray()
        # info: protect + original + archived + 名字（无长度前缀，与实测布局一致）
        info = struct.pack("<IQQ", 0, orig, arch) + nb
        file_body += b"info" + struct.pack("<Q", len(info)) + info
        # segm: flag + offset + original + archived
        segm = struct.pack("<IQQQ", flag, off, orig, arch)
        file_body += b"segm" + struct.pack("<Q", len(segm)) + segm
        # time
        tm = struct.pack("<Q", mtime)
        file_body += b"time" + struct.pack("<Q", len(tm)) + tm
        # adlr
        ad = struct.pack("<I", _z.adler32(bytes(nb)) & 0xFFFFFFFF)
        file_body += b"adlr" + struct.pack("<Q", len(ad)) + ad
        index += b"File" + struct.pack("<Q", len(file_body)) + file_body

    zidx = zlib.compress(bytes(index), 6)
    idx_at = len(data)
    data += b"\x01" + struct.pack("<QQ", len(zidx), len(index)) + zidx

    # 头部直接写入 data 前缀（0x00-0x27），随后整体落盘
    data[0:11] = MAGIC
    struct.pack_into("<Q", data, 11, 0x17)     # 一级索引指向 0x17
    data[0x17:0x1B] = b"\x80\x00\x00\x00"      # 0x80: 二级标记
    struct.pack_into("<Q", data, 0x20, idx_at) # 真实索引偏移
    f.write(bytes(data))
    return len(placed)
