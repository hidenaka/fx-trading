"""5ETFのメタデータ・セクター分類・流動性順位."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EtfMeta:
    """ETF1本のメタデータ."""

    symbol: str
    name: str
    sector_class: str
    tech_pct: float


UNIVERSE: tuple[EtfMeta, ...] = (
    EtfMeta("SPY", "SPDR S&P 500 ETF", "broad", 0.30),
    EtfMeta("QQQ", "Invesco QQQ Trust", "tech-heavy", 0.50),
    EtfMeta("IWM", "iShares Russell 2000", "small-cap", 0.05),
    EtfMeta("DIA", "SPDR Dow Jones 30", "broad-defensive", 0.20),
    EtfMeta("XLK", "Technology Select Sector SPDR", "tech-pure", 0.95),
)

_BY_SYMBOL: dict[str, EtfMeta] = {e.symbol: e for e in UNIVERSE}


def get_etf_meta(symbol: str) -> EtfMeta:
    """ETFメタデータを返す。未知の銘柄は KeyError."""
    return _BY_SYMBOL[symbol]


def liquidity_priority() -> list[str]:
    """流動性の高い順に並べた銘柄リスト（同点エントリー時の優先順位）.

    実測出来高ベース：SPY > QQQ > XLK > IWM > DIA
    （v1.1 で誤って DIA > XLK と書いていたものを v2.0 で訂正）
    """
    return ["SPY", "QQQ", "XLK", "IWM", "DIA"]


def macro_defense_followers() -> list[str]:
    """SPYが200日MA下のとき取引停止すべき銘柄リスト.

    v2.0方針：QQQ/XLK/DIA に加え、IWM も停止（小型株は弱気相場で先行下落）.
    """
    return ["QQQ", "XLK", "DIA", "IWM"]
