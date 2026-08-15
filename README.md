# Monitor de Mercado em Streamlit

Esta versão é um app Streamlit independente para USD/JPY, Nasdaq 100 e XAU/USD. Quando a sessão semanal de Forex está aberta, o app busca candles e spot reais na Twelve Data. Quando está fechado, ele não gera preços artificiais, não consulta a API e mantém o último snapshot válido congelado na tela.

## Execução local

```bash
cd /home/ubuntu/monitor-streamlit
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edite .streamlit/secrets.toml e coloque a sua chave
streamlit run app.py
```

O arquivo `secrets.toml` é local e não deve ser versionado. Na Streamlit Community Cloud, configure `TWELVEDATA_API_KEY` e, se necessário, `TWELVEDATA_SYMBOL_US100` em **Advanced settings → Secrets**.

## Teste do calendário Forex

```bash
python3 test_market_hours.py
```

A regra implementada acompanha a sessão semanal padrão de Forex em horário de Nova York: abertura no domingo às 17:00 e fechamento na sexta-feira às 17:00. `zoneinfo` trata automaticamente EST/EDT. Feriados, pausas extraordinárias e horários próprios de corretoras não são inferidos pela regra; nesses casos, o retorno real da Twelve Data continua sendo a autoridade para os candles.

## Comportamento de segurança

O app distingue `FEED REAL TWELVE DATA` de `ÚLTIMO PREÇO CONGELADO`. Erros de autenticação, permissão, símbolo, limite de requisições, indisponibilidade e timeout são exibidos ao usuário. Não há fallback aleatório e nenhuma chave é impressa em logs, links ou gráficos.
