"""请求/响应模型与输入校验。

校验规则（不满足时由 FastAPI 渲染为 HTTP 422，detail 中带字段位置 loc）：
- target_length: 1..512 的整数
- fragments: 2..28 个
- 每个片段: id 非空唯一; offset >= 0; payload_hex 为偶数长度的非空十六进制;
  weight 为 1..1_000_000 的整数
- 跨字段: 编号不得重复; 片段不得越过 target_length
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HEX_RE = re.compile(r"^(?:0x)?[0-9a-fA-F]+$")

Status = Literal["UNIQUE", "AMBIGUOUS", "IMPOSSIBLE"]
ImpossibleReason = Literal["GAP", "CONFLICT"]


class FragmentIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=128, description="片段唯一编号")
    offset: int = Field(ge=0, description="相对正文起点的零基偏移")
    payload_hex: str = Field(min_length=1, description="非空十六进制载荷（偶数位）")
    weight: int = Field(ge=1, le=1_000_000, description="可信权重 1..1000000")

    @field_validator("payload_hex")
    @classmethod
    def _validate_payload(cls, v: str) -> str:
        s = v.strip()
        if s.startswith(("0x", "0X")):
            s = s[2:]
        if not _HEX_RE.match(s):
            raise ValueError("payload_hex 必须是十六进制字符（0-9 a-f）")
        if len(s) % 2 != 0:
            raise ValueError("payload_hex 十六进制位数必须为偶数（整数字节）")
        return s.lower()

    @field_validator("id")
    @classmethod
    def _strip_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("片段编号不能为空")
        return s


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_length: int = Field(ge=1, le=512, description="目标正文长度（字节）")
    fragments: list[FragmentIn] = Field(min_length=2, max_length=28)


class ConflictSide(BaseModel):
    fragment_id: str
    offset: int


class Conflict(BaseModel):
    a: ConflictSide
    b: ConflictSide
    first_position: int
    positions: list[int]
    byte_a: str
    byte_b: str


class BodyWitness(BaseModel):
    body_hex: str
    witness_fragment_ids: list[str]


class AnalyzeResponse(BaseModel):
    status: Status
    target_length: int
    optimal_weight: Optional[int]
    optimal_fragment_count: Optional[int]
    impossible_reason: Optional[ImpossibleReason]
    bodies: list[BodyWitness]
    conflicts: list[Conflict]
