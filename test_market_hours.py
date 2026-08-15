from datetime import datetime
from zoneinfo import ZoneInfo

from market_hours import forex_market_status

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def check(label: str, value: bool) -> None:
    if not value:
        raise AssertionError(label)
    print(f"OK: {label}")


def main() -> None:
    check("sábado fechado", not forex_market_status(datetime(2026, 8, 15, 12, tzinfo=NY)).is_open)
    check("domingo antes da abertura fechado", not forex_market_status(datetime(2026, 8, 16, 16, 59, tzinfo=NY)).is_open)
    check("domingo às 17:00 aberto", forex_market_status(datetime(2026, 8, 16, 17, 0, tzinfo=NY)).is_open)
    check("sexta antes do fechamento aberto", forex_market_status(datetime(2026, 8, 14, 16, 59, tzinfo=NY)).is_open)
    check("sexta às 17:00 fechado", not forex_market_status(datetime(2026, 8, 14, 17, 0, tzinfo=NY)).is_open)
    check("sábado em UTC continua fechado", not forex_market_status(datetime(2026, 8, 15, 16, tzinfo=UTC)).is_open)

    # Agosto está em EDT (UTC-4); janeiro está em EST (UTC-5).
    summer = forex_market_status(datetime(2026, 8, 16, 21, 0, tzinfo=UTC))
    winter = forex_market_status(datetime(2026, 1, 4, 22, 0, tzinfo=UTC))
    check("DST de verão: domingo 21:00 UTC abre", summer.is_open)
    check("inverno: domingo 22:00 UTC abre", winter.is_open)
    print("Todos os testes de sessão Forex passaram.")


if __name__ == "__main__":
    main()
