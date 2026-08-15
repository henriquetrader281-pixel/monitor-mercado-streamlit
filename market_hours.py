"""Regras determinísticas para a sessão semanal de Forex.

A sessão padrão acompanha 17:00 de Nova York no domingo até 17:00 de
Nova York na sexta-feira. O uso de ZoneInfo torna a regra sensível ao DST.
Feriados e pausas específicas de corretoras não são inferidos aqui.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


@dataclass(frozen=True)
class MarketStatus:
    is_open: bool
    label: str
    reason: str
    local_time: datetime
    next_open: datetime | None = None
    next_close: datetime | None = None


def _as_new_york(value: datetime | None) -> datetime:
    current = value or datetime.now(tz=UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(NEW_YORK)


def _boundary(day_value, boundary: time) -> datetime:
    return datetime.combine(day_value, boundary, tzinfo=NEW_YORK)


def forex_market_status(now: datetime | None = None) -> MarketStatus:
    """Retorna se o Forex está aberto na sessão semanal global.

    A regra é baseada no horário de Nova York (domingo 17:00 a sexta 17:00),
    que muda automaticamente entre EST e EDT. A função não consulta a API e é
    adequada para testes unitários e para bloquear polling fora da sessão.
    """
    local = _as_new_york(now)
    weekday = local.weekday()  # segunda=0 ... domingo=6
    current_time = local.timetz().replace(tzinfo=None)
    sunday_open = time(17, 0)
    friday_close = time(17, 0)

    if weekday == 5 or weekday == 6:
        if weekday == 6 and current_time >= sunday_open:
            next_close = _boundary(local.date() + timedelta(days=5), friday_close)
            return MarketStatus(True, "MERCADO ABERTO", "Sessão semanal de Forex aberta no domingo", local, next_close=next_close)
        days_until_sunday = (6 - weekday) % 7 or 7
        next_open = _boundary(local.date() + timedelta(days=days_until_sunday), sunday_open)
        return MarketStatus(False, "MERCADO FECHADO", "Fim de semana: Forex reabre no domingo às 17:00 de Nova York", local, next_open=next_open)

    if weekday == 4 and current_time >= friday_close:
        next_open = _boundary(local.date() + timedelta(days=2), sunday_open)
        return MarketStatus(False, "MERCADO FECHADO", "Fechamento semanal: Forex reabre no domingo às 17:00 de Nova York", local, next_open=next_open)

    next_close = _boundary(local.date() + timedelta(days=(4 - weekday) % 7), friday_close)
    return MarketStatus(True, "MERCADO ABERTO", "Dentro da sessão semanal de Forex", local, next_close=next_close)


def is_forex_market_open(now: datetime | None = None) -> bool:
    return forex_market_status(now).is_open


if __name__ == "__main__":
    status = forex_market_status()
    print(status.label, "—", status.reason, "—", status.local_time.isoformat())
