# -*- coding: utf-8 -*-
"""Ruby Marshal 4.8 编解码器（纯 Python、零依赖）
================================================
RPG Maker VX Ace / VX / XP 的 Data/*.rvdata2（XP 为 .rxdata）是 Ruby Marshal
二进制序列化格式。本模块实现完整的读取与回写：

- 读取：解析成节点树（保留对象/符号链接身份、字符串编码 ivar、UserDef 原始字节）
- 回写：与 Ruby marshal.c 完全一致的注册顺序 → 未修改的文件字节级还原
- 翻译：直接就地修改 MStr.data（保持节点身份）→ 链接表/符号表永不失效

格式参考：Ruby 源码 marshal.c（4.8 版协议，1.9~3.x 稳定不变）。

Wire 格式速查：
  头: 04 08
  '0' nil   'T' true   'F' false
  'i' Fixnum: 0→00 | 1..122→n+5 | -123..-1→n-5 | 大数→[1..4|FC..FF][|n| LE 幅值]
  长度(w_long): 0→00 | 1..4→n+5 | -4..-1→n-5 | 其余→[1..4|FC..FF][补码 LE]
  ':' 新符号(注册)   ';' 符号链接   '@' 对象链接
  '"' 字符串   'I' ivar 包裹   '[' 数组   '{' Hash   '}' 带默认值 Hash
  'o' Object   'u' UserDef(_dump 原始字节)   'U' UserMarshal   'S' Struct
  'e' 扩展模块   'C' 类名变更   'c' 类引用   'm' 模块引用
  'f' Float(原始文本+\0)   'l' Bignum(符号+limb)

注册顺序（决定链接索引，两端一致，参照 rubymarshal/实测）：
  所有堆对象（字符串/数组/Hash/'o'/'S'/'u'/'U'/'l'）读到类型字节后立即入口注册
  → 自引用/循环引用天然成立；'e'/'C' 包裹不注册（内层对象自己注册）
"""

MAG_VER = b"\x04\x08"


class MNode:
    __slots__ = ()

class MSingleton(MNode):
    __slots__ = ()
    def __repr__(self):
        return self.__class__.__name__

NIL = MSingleton()          # noqa: E741  对应 Ruby nil
TRUE = MSingleton()
FALSE = MSingleton()


class MInt(MNode):
    __slots__ = ("v",)
    def __init__(self, v):
        self.v = v
    def __repr__(self):
        return repr(self.v)


class MFloat(MNode):
    __slots__ = ("raw",)     # 原始字节（不含结尾 \0），回写保持原样
    def __init__(self, raw):
        self.raw = raw


class MBigNum(MNode):
    __slots__ = ("sign", "limbs")   # sign: b'+' / b'-'，limbs: 原始字节
    def __init__(self, sign, limbs):
        self.sign = sign
        self.limbs = limbs


class MSym(MNode):
    __slots__ = ("name",)
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return f":{self.name}"


class MStr(MNode):
    __slots__ = ("data", "ivars")   # data: bytes；ivars: [(MSym, node)] | None
    def __init__(self, data, ivars=None):
        self.data = data
        self.ivars = ivars

    def encoding(self):
        """按 Marshal 编码 ivar 推断：E=T→utf-8，E=F→None(binary)，u→编码名。"""
        for k, v in self.ivars or []:
            if k.name == "E":
                return "utf-8" if v is TRUE else None
            if k.name == "u" and isinstance(v, MStr):
                try:
                    return v.data.decode("ascii")
                except Exception:
                    return "utf-8"
        return "utf-8"

    def decode(self, enc=None):
        enc = enc or self.encoding() or "utf-8"
        try:
            return self.data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            if enc != "cp932":
                try:
                    return self.data.decode("cp932")
                except UnicodeDecodeError:
                    pass
            return self.data.decode("utf-8", "replace")

    @staticmethod
    def set_text(node, text):
        """就地修改 MStr 内容（保持节点身份→链接不变）。返回 True=成功。"""
        enc = node.encoding()
        if enc is None:
            return False                      # 二进制串不碰
        try:
            node.data = text.encode(enc)
        except (UnicodeEncodeError, LookupError):
            try:
                node.data = text.encode("utf-8")
                for i, (k, v) in enumerate(node.ivars or []):
                    if k.name == "E" and v is FALSE:
                        node.ivars[i] = (k, TRUE)
            except UnicodeEncodeError:
                return False
        return True


class MArray(MNode):
    __slots__ = ("items", "ivars")
    def __init__(self, items=None, ivars=None):
        self.items = items if items is not None else []
        self.ivars = ivars


class MHash(MNode):
    __slots__ = ("pairs", "default", "ivars")
    def __init__(self, pairs=None, default=None, ivars=None):
        self.pairs = pairs if pairs is not None else []
        self.default = default
        self.ivars = ivars


class MObj(MNode):
    __slots__ = ("cls", "ivars")
    def __init__(self, cls, ivars):
        self.cls = cls
        self.ivars = ivars
    def ivar(self, name):
        for k, v in self.ivars:
            if k.name == name:
                return v
        return None


class MUserDef(MNode):
    __slots__ = ("cls", "data")       # Table/Rect/Color/Tone 等 _dump 原始字节
    def __init__(self, cls, data):
        self.cls = cls
        self.data = data


class MUserMarshal(MNode):
    __slots__ = ("cls", "obj")
    def __init__(self, cls, obj):
        self.cls = cls
        self.obj = obj


class MStruct(MNode):
    __slots__ = ("cls", "members")
    def __init__(self, cls, members):
        self.cls = cls
        self.members = members


class MExt(MNode):
    __slots__ = ("mod", "obj")       # 'e' 扩展模块
    def __init__(self, mod, obj):
        self.mod = mod
        self.obj = obj


class MClassChange(MNode):
    __slots__ = ("cls", "obj")       # 'C' 类名变更
    def __init__(self, cls, obj):
        self.cls = cls
        self.obj = obj


class MIvarWrap(MNode):
    __slots__ = ("obj", "ivars")     # 'I' 包裹的非 Str/Array/Hash 节点（罕见）
    def __init__(self, obj, ivars):
        self.obj = obj
        self.ivars = ivars


class MClassRef(MNode):
    __slots__ = ("sym", "kind")      # 'c' 类 / 'm' 模块
    def __init__(self, sym, kind):
        self.sym = sym
        self.kind = kind


# ---------------------------------------------------------------- 读取
class Reader:
    def __init__(self, data):
        self.b = data
        self.p = 0
        self.syms = []               # 符号表（':' 注册）
        self.sym_intern = {}
        self.objs = []               # 对象表（按各类型既定时机注册）

    def u8(self):
        c = self.b[self.p]
        self.p += 1
        return c

    def take(self, n):
        d = self.b[self.p:self.p + n]
        if len(d) != n:
            raise ValueError("marshal 数据截断")
        self.p += n
        return d

    def r_long(self):
        """w_long 逆：与 Fixnum 编码同源（marshal.c 同一函数）
        小值 1..122→n+5 | -123..-1→n-5 | 其余 [count 1..4|FC..FF][LE 幅值]"""
        x = self.u8()
        if x == 0:
            return 0
        if 6 <= x <= 0x7F:
            return x - 5
        if 0x80 <= x <= 0xFA:
            return x - 251
        c = x - 256 if x >= 0x80 else x
        mag = int.from_bytes(self.take(abs(c)), "little")
        return mag if c > 0 else -mag

    def r_fixnum(self):
        """'i' 后的 Fixnum：小值阈值 122/-123，大值为符号+幅值"""
        x = self.u8()
        if x == 0:
            return 0
        if 6 <= x <= 0x7F:
            return x - 5
        if 0x80 <= x <= 0xFA:
            return x - 251
        c = x - 256 if x >= 0x80 else x
        mag = int.from_bytes(self.take(abs(c)), "little")
        return mag if c > 0 else -mag

    def r_bytes(self):
        return self.take(self.r_long())

    def r_ivars(self):
        out = []
        for _ in range(self.r_long()):
            k = self.r_node()
            if not isinstance(k, MSym):
                raise ValueError("ivar 键不是符号")
            out.append((k, self.r_node()))
        return out

    def r_node(self):
        t = self.u8()
        if t == 0x30:
            return NIL
        if t == 0x54:
            return TRUE
        if t == 0x46:
            return FALSE
        if t == 0x69:                          # 'i'
            return MInt(self.r_fixnum())
        if t == 0x66:                          # 'f'
            end = self.b.index(b"\x00", self.p)
            raw = self.b[self.p:end]
            self.p = end + 1
            return MFloat(raw)
        if t == 0x6C:                          # 'l'
            self.objs.append(None)
            sign = self.take(1)
            n = self.r_long()
            node = MBigNum(sign, self.take(n * 2))
            self.objs[-1] = node
            return node
        if t == 0x3A:                          # ':' 新符号（注册）
            name = self.r_bytes().decode("utf-8", "replace")
            s = self.sym_intern.get(name)
            if s is None:
                s = MSym(name)
                self.sym_intern[name] = s
            self.syms.append(s)
            return s
        if t == 0x3B:                          # ';' 符号链接
            return self.syms[self.r_long()]
        if t == 0x40:                          # '@' 对象链接
            return self.objs[self.r_long()]
        if t == 0x22:                          # '"' 字符串：入口即注册
            self.objs.append(None)
            node = MStr(self.r_bytes())
            self.objs[-1] = node
            return node
        if t == 0x49:                          # 'I' ivar 包裹（内层自己注册）
            inner = self.r_node()
            ivars = self.r_ivars()
            if isinstance(inner, (MStr, MArray, MHash)):
                inner.ivars = ivars
                return inner
            return MIvarWrap(inner, ivars)
        if t == 0x5B:                          # '[' 数组：分配后先注册（支持自引用）
            node = MArray()
            self.objs.append(node)
            for _ in range(self.r_long()):
                node.items.append(self.r_node())
            return node
        if t == 0x7B or t == 0x7D:             # '{' '}' Hash
            node = MHash()
            self.objs.append(node)
            for _ in range(self.r_long()):
                k = self.r_node()
                node.pairs.append((k, self.r_node()))
            if t == 0x7D:
                node.default = self.r_node()
            return node
        if t == 0x6F:                          # 'o' Object：先建节点再填充（循环引用安全）
            cls = self.r_node()
            node = MObj(cls, [])
            self.objs.append(node)
            node.ivars = self.r_ivars()
            return node
        if t == 0x75:                          # 'u' UserDef
            cls = self.r_node()
            node = MUserDef(cls, self.r_bytes())
            self.objs.append(node)
            return node
        if t == 0x55:                          # 'U' UserMarshal：先建再填充
            cls = self.r_node()
            node = MUserMarshal(cls, None)
            self.objs.append(node)
            node.obj = self.r_node()
            return node
        if t == 0x53:                          # 'S' Struct：先建再填充
            cls = self.r_node()
            node = MStruct(cls, [])
            self.objs.append(node)
            for _ in range(self.r_long()):
                k = self.r_node()
                node.members.append((k, self.r_node()))
            return node
        if t == 0x65:                          # 'e' 扩展模块（不注册）
            return MExt(self.r_node(), self.r_node())
        if t == 0x43:                          # 'C' 类名变更（不注册）
            return MClassChange(self.r_node(), self.r_node())
        if t == 0x63:                          # 'c' 类引用
            return MClassRef(self.r_node(), "c")
        if t == 0x6D:                          # 'm' 模块引用
            return MClassRef(self.r_node(), "m")
        raise ValueError(f"未知 marshal 类型字节 0x{t:02x} @ {self.p - 1}")


def loads(data):
    """解析 Marshal 字节 → 节点树。"""
    if data[:2] != MAG_VER:
        raise ValueError(f"不是 Marshal 4.8 文件（头={data[:2].hex()}）")
    r = Reader(data)
    r.p = 2
    node = r.r_node()
    if r.p != len(r.b):
        raise ValueError(f"尾部多余字节：{len(r.b) - r.p}")
    return node


# ---------------------------------------------------------------- 回写
def _w_long(out, x):
    """w_long：与 Fixnum 同一编码（marshal.c 同一函数）。
    0→00 | 1..122→n+5 | -123..-1→n-5 | 其余 [count 1..4|FC..FF][幅值 LE]"""
    if x == 0:
        out.append(0)
    elif 0 < x < 123:
        out.append(x + 5)
    elif -124 < x < 0:
        out.append((x - 5) & 0xFF)
    else:
        mag = abs(x)
        n = (mag.bit_length() + 7) // 8 or 1
        out.append(n if x > 0 else (256 - n) & 0xFF)
        out.extend(mag.to_bytes(n, "little"))


def _w_fixnum(out, x):
    if x == 0:
        out.append(0)
    elif 0 < x < 123:
        out.append(x + 5)
    elif -124 < x < 0:
        out.append((x - 5) & 0xFF)
    else:
        mag = abs(x)
        n = (mag.bit_length() + 7) // 8 or 1
        out.append(n if x > 0 else (256 - n) & 0xFF)
        out.extend(mag.to_bytes(n, "little"))


class Writer:
    def __init__(self):
        self.out = bytearray(MAG_VER)
        self.sym_seen = {}      # 符号名 → 索引（Ruby 符号表按名字 intern）
        self.obj_seen = {}      # id(node) → 索引（对象按身份）

    def _reg_sym(self, s):
        if s.name in self.sym_seen:
            self.out.append(0x3B)                       # ';'
            _w_long(self.out, self.sym_seen[s.name])
            return
        b = s.name.encode("utf-8")
        self.out.append(0x3A)                           # ':'
        _w_long(self.out, len(b))
        self.out.extend(b)
        self.sym_seen[s.name] = len(self.sym_seen)

    def _reg_obj(self, node):
        self.obj_seen[id(node)] = len(self.obj_seen)

    def _linkable(self, node):
        if id(node) in self.obj_seen:
            self.out.append(0x40)                       # '@'
            _w_long(self.out, self.obj_seen[id(node)])
            return True
        return False

    def _w_ivars(self, ivars):
        _w_long(self.out, len(ivars))
        for k, v in ivars:
            self._w_node(k)
            self._w_node(v)

    def _w_node(self, n):
        if n is NIL:
            self.out.append(0x30)
            return
        if n is TRUE:
            self.out.append(0x54)
            return
        if n is FALSE:
            self.out.append(0x46)
            return
        if isinstance(n, MInt):
            self.out.append(0x69)
            _w_fixnum(self.out, n.v)
            return
        if isinstance(n, MSym):
            self._reg_sym(n)
            return
        if isinstance(n, MFloat):
            self.out.append(0x66)
            self.out.extend(n.raw)
            self.out.append(0)
            return
        if isinstance(n, MBigNum):
            if self._linkable(n):
                return
            self._reg_obj(n)                          # 入口注册
            self.out.append(0x6C)
            self.out.extend(n.sign)
            _w_long(self.out, len(n.limbs) // 2)
            self.out.extend(n.limbs)
            return
        if isinstance(n, MStr):
            if self._linkable(n):
                return
            self._reg_obj(n)                          # 入口注册（无子节点，位置等价）
            if n.ivars:
                self.out.append(0x49)
            self.out.append(0x22)
            _w_long(self.out, len(n.data))
            self.out.extend(n.data)
            if n.ivars:
                self._w_ivars(n.ivars)
            return
        if isinstance(n, MArray):
            if self._linkable(n):
                return
            if n.ivars:
                self.out.append(0x49)
            self.out.append(0x5B)
            _w_long(self.out, len(n.items))
            self._reg_obj(n)                            # 长度后、元素前注册
            for it in n.items:
                self._w_node(it)
            if n.ivars:
                self._w_ivars(n.ivars)
            return
        if isinstance(n, MHash):
            if self._linkable(n):
                return
            if n.ivars:
                self.out.append(0x49)
            self.out.append(0x7D if n.default is not None else 0x7B)
            _w_long(self.out, len(n.pairs))
            self._reg_obj(n)
            for k, v in n.pairs:
                self._w_node(k)
                self._w_node(v)
            if n.default is not None:
                self._w_node(n.default)
            if n.ivars:
                self._w_ivars(n.ivars)
            return
        if isinstance(n, MObj):
            if self._linkable(n):
                return
            self._reg_obj(n)                          # 入口注册（支持自引用）
            self.out.append(0x6F)
            self._w_node(n.cls)
            self._w_ivars(n.ivars)
            return
        if isinstance(n, MUserDef):
            if self._linkable(n):
                return
            self._reg_obj(n)
            self.out.append(0x75)
            self._w_node(n.cls)
            _w_long(self.out, len(n.data))
            self.out.extend(n.data)
            return
        if isinstance(n, MUserMarshal):
            if self._linkable(n):
                return
            self._reg_obj(n)
            self.out.append(0x55)
            self._w_node(n.cls)
            self._w_node(n.obj)
            return
        if isinstance(n, MStruct):
            if self._linkable(n):
                return
            self._reg_obj(n)
            self.out.append(0x53)
            self._w_node(n.cls)
            _w_long(self.out, len(n.members))
            for k, v in n.members:
                self._w_node(k)
                self._w_node(v)
            return
        if isinstance(n, MExt):
            self.out.append(0x65)
            self._w_node(n.mod)
            self._w_node(n.obj)
            return
        if isinstance(n, MClassChange):
            self.out.append(0x43)
            self._w_node(n.cls)
            self._w_node(n.obj)
            return
        if isinstance(n, MIvarWrap):
            self.out.append(0x49)
            self._w_node(n.obj)
            self._w_ivars(n.ivars)
            return
        if isinstance(n, MClassRef):
            self.out.append(0x63 if n.kind == "c" else 0x6D)
            self._w_node(n.sym)
            return
        raise TypeError(f"无法序列化节点 {type(n).__name__}")

    def getvalue(self):
        return bytes(self.out)


def dumps(node):
    w = Writer()
    w._w_node(node)
    return w.getvalue()
