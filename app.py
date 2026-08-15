from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from market_hours import forex_market_status

API_URL = "https://api.twelvedata.com"
BRASILIA = ZoneInfo("America/Sao_Paulo")
ASSETS = {
    "USD/JPY": {"symbol": "USD/JPY", "precision": 3},
    "US100 / Nasdaq 100": {"symbol": "NDX", "precision": 2},
    "XAU/USD": {"symbol": "XAU/USD", "precision": 2},
}
INTERVALS = {"M5": "5min", "M15": "15min", "H1": "1h", "H4": "4h", "D1": "1day"}


def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default) or "").strip()
    except Exception:
        return default


def configured_symbol(asset_name: str) -> str:
    secret_name = "TWELVEDATA_SYMBOL_US100" if asset_name.startswith("US100") else f"TWELVEDATA_SYMBOL_{asset_name.replace('/', '')}"
    return get_secret(secret_name, ASSETS[asset_name]["symbol"])


def api_error_message(response: requests.Response, payload: Any) -> str:
    messages = {
        401: "chave Twelve Data inválida ou ausente",
        403: "o plano Twelve Data não permite este instrumento ou endpoint",
        404: "símbolo não encontrado; confirme o ticker nas configurações da Twelve Data",
        429: "limite da Twelve Data atingido; aguardando o próximo refresh",
    }
    if response.status_code in messages:
        return messages[response.status_code]
    if response.status_code >= 500:
        return "Twelve Data indisponível temporariamente"
    return str(payload.get("message") or payload.get("code") or f"erro HTTP {response.status_code}") if isinstance(payload, dict) else f"erro HTTP {response.status_code}"


def parse_values(payload: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in payload.get("values", []):
        try:
            rows.append({
                "time": pd.to_datetime(item["datetime"]),
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": float(item.get("volume") or 0),
            })
        except (KeyError, TypeError, ValueError):
            continue
    if not rows:
        raise RuntimeError("Twelve Data não retornou candles válidos")
    return pd.DataFrame(rows).sort_values("time").reset_index(drop=True)


@st.cache_data(ttl=10, show_spinner=False)
def fetch_twelve_data(symbol: str, interval: str, outputsize: int, _api_key: str) -> tuple[pd.DataFrame, float, str]:
    if not _api_key:
        raise RuntimeError("TWELVEDATA_API_KEY não configurada")
    headers = {"Authorization": f"apikey {_api_key}"}
    candle_params = {"symbol": symbol, "interval": interval, "outputsize": outputsize, "order": "asc", "timezone": "America/Sao_Paulo"}
    candle_response = requests.get(f"{API_URL}/time_series", params=candle_params, headers=headers, timeout=12)
    try:
        candle_payload = candle_response.json()
    except ValueError as exc:
        raise RuntimeError("resposta inválida da Twelve Data") from exc
    if candle_response.status_code != 200 or "values" not in candle_payload:
        raise RuntimeError(api_error_message(candle_response, candle_payload))
    frame = parse_values(candle_payload)

    quote_response = requests.get(f"{API_URL}/quote", params={"symbol": symbol}, headers=headers, timeout=12)
    try:
        quote_payload = quote_response.json()
    except ValueError:
        quote_payload = {}
    if quote_response.status_code not in (200, 204) and quote_response.status_code in (401, 403, 404, 429):
        raise RuntimeError(api_error_message(quote_response, quote_payload))
    raw_spot = quote_payload.get("price") or quote_payload.get("close") or frame.iloc[-1]["close"]
    try:
        spot = float(raw_spot)
    except (TypeError, ValueError):
        spot = float(frame.iloc[-1]["close"])
    return frame, spot, "FEED REAL TWELVE DATA"


def indicators(frame: pd.DataFrame) -> dict[str, float]:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    volume = frame["volume"].clip(lower=0)
    total_volume = float(volume.sum())
    vwap = float((typical * volume).sum() / total_volume) if total_volume else float(frame.iloc[-1]["close"])
    poc = float(frame.loc[volume.idxmax(), "close"]) if total_volume else vwap
    return {"vwap": vwap, "poc": poc, "ma9": float(frame["close"].tail(9).mean()), "ma21": float(frame["close"].tail(21).mean())}


def fmt(value: float | None, precision: int) -> str:
    return "—" if value is None else f"{value:,.{precision}f}"


def render_24h_chart(frame: pd.DataFrame, symbol: str, precision: int) -> None:
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=frame["time"], y=frame["close"], mode="lines+markers", name=symbol, line=dict(color="#2ee59d", width=2), marker=dict(size=4)))
    figure.update_layout(height=320, template="plotly_dark", margin=dict(l=10, r=10, t=35, b=10), title="Histórico das últimas 24 horas", yaxis=dict(tickformat=f",.{precision}f"), hovermode="x unified")
    st.plotly_chart(figure, use_container_width=True)


def render_candles(frame: pd.DataFrame, symbol: str) -> None:
    figure = go.Figure(go.Candlestick(x=frame["time"], open=frame["open"], high=frame["high"], low=frame["low"], close=frame["close"], name=symbol))
    figure.update_layout(height=520, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10), xaxis_rangeslider_visible=False)
    st.plotly_chart(figure, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Monitor de Mercado", page_icon="📈", layout="wide")
    st.title("Monitor de Mercado")
    st.caption("Parâmetros alinhados ao monitor Manus: ativo, timeframe, feed real, sessão, spot, indicadores e histórico.")

    status = forex_market_status()
    with st.sidebar:
        st.header("Configurações")
        asset_name = st.selectbox("Ativo", list(ASSETS))
        timeframe = st.selectbox("Timeframe", list(INTERVALS))
        market_session = st.selectbox("Sessão", ["Global", "Pacífico", "Tóquio", "Londres", "Nova York"])
        auto_refresh = st.checkbox("Auto-refresh quando aberto", value=True)
        refresh_seconds = st.number_input("Refresh quando aberto (segundos)", min_value=10, max_value=300, value=30, step=5)
        if st.button("Atualizar agora", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.divider()
        st.code('TWELVEDATA_API_KEY = "sua-chave"\nTWELVEDATA_SYMBOL_US100 = "NDX"', language="toml")

    if status.is_open and auto_refresh:
        st_autorefresh(interval=int(refresh_seconds * 1000), key=f"market-refresh-{asset_name}-{timeframe}-{market_session}")
        st.success(f"{status.label} · {status.reason} · {status.local_time:%d/%m/%Y %H:%M:%S %Z}")
    else:
        st.warning(f"{status.label} · {status.reason}. O último preço permanece congelado e não há novas requisições.")

    st.caption(f"Sessão selecionada: {market_session}")
    api_key = get_secret("TWELVEDATA_API_KEY")
    symbol = configured_symbol(asset_name)
    precision = ASSETS[asset_name]["precision"]
    snapshot_key = f"{asset_name}:{timeframe}"
    st.session_state.setdefault("snapshots", {})
    st.session_state.setdefault("errors", {})
    snapshot = st.session_state.snapshots.get(snapshot_key)

    frame = history_24h = spot = None
    feed_mode = ""
    if status.is_open:
        try:
            frame, spot, feed_mode = fetch_twelve_data(symbol, INTERVALS[timeframe], 100, api_key)
            history_24h, _, _ = fetch_twelve_data(symbol, "1h", 24, api_key)
            fetched_at = datetime.now(BRASILIA)
            snapshot = {"frame": frame, "history_24h": history_24h, "spot": spot, "feed_mode": feed_mode, "fetched_at": fetched_at}
            st.session_state.snapshots[snapshot_key] = snapshot
            st.session_state.errors[snapshot_key] = ""
        except Exception as exc:
            st.session_state.errors[snapshot_key] = str(exc)
    if not status.is_open and snapshot:
        frame, history_24h, spot = snapshot["frame"], snapshot["history_24h"], snapshot["spot"]
        feed_mode = "ÚLTIMO PREÇO CONGELADO"
    elif snapshot and frame is None:
        frame, history_24h, spot, feed_mode = snapshot["frame"], snapshot["history_24h"], snapshot["spot"], "ÚLTIMO SNAPSHOT VÁLIDO"

    error = st.session_state.errors.get(snapshot_key, "")
    if frame is None:
        st.error(f"Não foi possível obter dados: {error or 'aguardando a primeira resposta da Twelve Data'}")
        return

    fetched_at = snapshot["fetched_at"]
    age_seconds = max(0, int((datetime.now(BRASILIA) - fetched_at).total_seconds()))
    age_label = "agora" if age_seconds < 60 else f"há {age_seconds // 60} min"
    status_color = "#2ee59d" if status.is_open and not error else "#f59e0b"
    st.markdown(f"<div style='padding:10px 14px;border:1px solid {status_color};border-radius:8px;margin:8px 0 16px;background:rgba(255,255,255,.03)'><span style='color:{status_color};font-size:18px'>●</span> <b>Última atualização: {fetched_at:%d/%m/%Y %H:%M:%S} BRT</b> · {age_label} · <b>{feed_mode}</b></div>", unsafe_allow_html=True)
    if not status.is_open:
        st.info(f"Histórico e cotação congelados desde {fetched_at:%d/%m/%Y %H:%M:%S} BRT.")
    elif error:
        st.warning(f"Falha no refresh; mantendo o snapshot anterior: {error}")

    metrics = indicators(frame)
    columns = st.columns(6)
    columns[0].metric("Taxa atual / Spot", fmt(spot, precision))
    columns[1].metric("VWAP", fmt(metrics["vwap"], precision))
    columns[2].metric("POC", fmt(metrics["poc"], precision))
    columns[3].metric("MA9", fmt(metrics["ma9"], precision))
    columns[4].metric("MA21", fmt(metrics["ma21"], precision))
    columns[5].metric("Variação 24h", f"{((float(history_24h.iloc[-1]['close']) / float(history_24h.iloc[0]['close']) - 1) * 100):+.2f}%")

    st.subheader(f"Taxa de câmbio e histórico — {symbol}")
    render_24h_chart(history_24h, symbol, precision)
    st.subheader(f"Gráfico {timeframe}")
    render_candles(frame.tail(80), symbol)
    st.dataframe(frame.tail(20), use_container_width=True, hide_index=True)

    if status.is_open:
        st.info(f"Próximo fechamento estimado: {status.next_close:%d/%m/%Y %H:%M %Z}. Pausas e feriados do provedor podem alterar essa previsão.")
    else:
        st.info(f"Próxima abertura estimada: {status.next_open:%d/%m/%Y %H:%M %Z}.")


if __name__ == "__main__":
    main()
