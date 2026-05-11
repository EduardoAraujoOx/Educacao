"""Gera o site estático em docs/index.html a partir dos resultados do Censo.

O objetivo é manter a página HTML sempre sincronizada com o CSV gerado pelo
workflow, evitando edição manual do painel.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
TABELA_PATH = BASE_DIR / "outputs" / "tabelas" / "es_af_tempo_integral_2015_2025.csv"
DOCS_DIR = BASE_DIR / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def fmt_int(x) -> str:
    if pd.isna(x):
        return ""
    return f"{int(round(float(x))):,}".replace(",", ".")


def fmt_pct(x) -> str:
    if pd.isna(x):
        return ""
    return f"{float(x):.1f}%".replace(".", ",")


def fmt_signed(x) -> str:
    if pd.isna(x):
        return ""
    val = int(round(float(x)))
    return f"{val:+,}".replace(",", ".")


def bar_height(value: float, max_value: float, min_height: int = 4) -> int:
    if pd.isna(value) or max_value <= 0:
        return min_height
    return max(min_height, int(round(float(value) / max_value * 100)))


def gerar_barras_estoque(df: pd.DataFrame, coluna: str, cor: str) -> str:
    max_v = df[coluna].max()
    partes = []
    for _, row in df.iterrows():
        h = bar_height(row[coluna], max_v)
        partes.append(
            f'<div class="bar-wrap"><div class="bar-label">{fmt_int(row[coluna])}</div>'
            f'<div class="bar {cor}" style="height:{h}%"></div>'
            f'<div class="bar-year">{int(row["ano"])}</div></div>'
        )
    return "\n".join(partes)


def gerar_barras_variacao(df: pd.DataFrame, coluna: str) -> str:
    vals = df[coluna].dropna().abs()
    max_v = vals.max() if not vals.empty else 1
    partes = []
    for _, row in df.dropna(subset=[coluna]).iterrows():
        val = row[coluna]
        h = bar_height(abs(val), max_v)
        cls = "green" if val >= 0 else "red"
        partes.append(
            f'<div class="bar-wrap"><div class="bar-label">{fmt_signed(val)}</div>'
            f'<div class="bar {cls}" style="height:{h}%"></div>'
            f'<div class="bar-year">{int(row["ano"])}</div></div>'
        )
    return "\n".join(partes)


def tabela_html(df: pd.DataFrame, colunas: list[tuple[str, str, str]]) -> str:
    thead = "".join(f"<th>{titulo}</th>" for _, titulo, _ in colunas)
    linhas = []
    for _, row in df.iterrows():
        cells = []
        for col, _, tipo in colunas:
            if tipo == "int":
                valor = fmt_int(row[col])
            elif tipo == "pct":
                valor = fmt_pct(row[col])
            elif tipo == "signed":
                valor = fmt_signed(row[col])
            else:
                valor = str(row[col])
            cells.append(f"<td>{valor}</td>")
        linhas.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(linhas)}</tbody></table>"


def main() -> None:
    if not TABELA_PATH.exists():
        raise FileNotFoundError(f"Tabela não encontrada: {TABELA_PATH}")

    df = pd.read_csv(TABELA_PATH)
    df = df.sort_values("ano").copy()

    # Mantém 2015 no arquivo completo, mas a visualização principal começa em 2016
    # para evitar que uma possível forma parcial de jornada ampliada distorça a leitura.
    df_principal = df[df["ano"] >= 2016].copy()
    if df_principal.empty:
        df_principal = df.copy()

    ultimo = df_principal.iloc[-1]
    ano_final = int(ultimo["ano"])
    ano_base = 2019 if 2019 in set(df_principal["ano"]) else int(df_principal.iloc[0]["ano"])
    base = df_principal[df_principal["ano"] == ano_base].iloc[0]

    crescimento_matriculas = (
        (ultimo["matriculas_estaduais_af_integral"] / base["matriculas_estaduais_af_integral"] - 1) * 100
        if base["matriculas_estaduais_af_integral"] else pd.NA
    )

    tabela_resumo = tabela_html(
        df_principal,
        [
            ("ano", "Ano", "int"),
            ("escolas_estaduais_com_af", "Escolas estaduais com AF", "int"),
            ("escolas_estaduais_com_af_integral", "Escolas estaduais AF integral", "int"),
            ("pct_escolas_estaduais_af_integral", "% escolas estaduais", "pct"),
            ("matriculas_estaduais_af", "Matrículas estaduais AF", "int"),
            ("matriculas_estaduais_af_integral", "Matrículas estaduais AF integral", "int"),
            ("pct_matriculas_estaduais_af_integral", "% matrículas estaduais", "pct"),
            ("escolas_municipais_com_af_integral", "Escolas municipais AF integral", "int"),
            ("matriculas_municipais_af_integral", "Matrículas municipais AF integral", "int"),
        ],
    )

    tabela_metodo = tabela_html(
        df_principal,
        [
            ("ano", "Ano", "int"),
            ("escolas_estaduais_com_af_integral", "Estoque tratado", "int"),
            ("var_liquida_escolas_estaduais_af_integral", "Variação líquida", "signed"),
            ("matriculas_estaduais_af_integral", "Matrículas integrais", "int"),
            ("var_liquida_matriculas_estaduais_af_integral", "Variação de matrículas", "signed"),
        ],
    )

    status_2025 = (
        "A tabela já inclui 2025."
        if 2025 in set(df["ano"])
        else "A tabela ainda não inclui 2025; nova execução do workflow deve completar esse ano se o processamento do arquivo de matrículas do Censo 2025 for concluído."
    )

    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Censo Escolar ES | Tempo Integral nos Anos Finais</title>
  <style>
    :root{{--bg:#f6f8fb;--card:#fff;--ink:#172033;--muted:#637083;--line:#d9e1ec;--blue:#1f5fbf;--green:#16805d;--red:#b94040;--soft:#eef4ff;--cream:#fff8e8}}
    *{{box-sizing:border-box}} body{{margin:0;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.45}}
    header{{background:linear-gradient(135deg,#0c1f4a 0%,#183f8c 100%);color:#fff;padding:42px 24px 34px}} .wrap{{max-width:1180px;margin:0 auto}}
    h1{{margin:0 0 10px;font-size:clamp(28px,4vw,44px);letter-spacing:-.02em}} .subtitle{{margin:0;max-width:900px;color:#dbe8ff;font-size:17px}}
    main{{padding:26px 24px 52px}} .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:22px 0}} .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px}} .method{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
    .card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 8px 20px rgba(31,44,71,.06)}} .note{{background:var(--cream);border:1px solid #f0d392;border-radius:14px;padding:14px 16px;color:#543700}}
    .kpi-label{{color:var(--muted);font-size:13px;margin-bottom:8px}} .kpi-value{{font-size:28px;font-weight:760;letter-spacing:-.02em}} .kpi-note{{margin-top:6px;color:var(--muted);font-size:12px}}
    section{{margin-top:22px}} h2{{font-size:22px;margin:0 0 12px;letter-spacing:-.01em}} .lead{{color:var(--muted);margin:0 0 14px}} .small{{color:var(--muted);font-size:13px}} .caption{{color:var(--muted);font-size:13px;margin-top:10px}}
    .method-step{{background:#f9fbff;border:1px solid var(--line);border-radius:14px;padding:15px}} .step-number{{width:28px;height:28px;border-radius:50%;background:#183f8c;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-weight:800;margin-right:8px}}
    .chart{{height:320px;display:flex;align-items:flex-end;gap:8px;border-left:1px solid var(--line);border-bottom:1px solid var(--line);padding:12px 10px 32px;position:relative}} .bar-wrap{{height:100%;flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:6px}} .bar{{width:70%;border-radius:7px 7px 0 0;background:var(--blue);min-height:2px}} .bar.green{{background:var(--green)}} .bar.red{{background:var(--red)}} .bar-label{{font-size:11px;color:var(--ink);font-weight:700}} .bar-year{{font-size:11px;color:var(--muted)}} .axis-note{{position:absolute;top:8px;left:12px;font-size:12px;color:var(--muted)}}
    .table-wrap{{overflow-x:auto;border-radius:14px;border:1px solid var(--line);background:#fff}} table{{border-collapse:collapse;width:100%;min-width:980px;font-size:14px}} th,td{{padding:11px 12px;border-bottom:1px solid #e9eef5;text-align:right}} th{{background:#eef3fa;color:#24324c;font-size:12px;text-transform:uppercase;letter-spacing:.03em}} td:first-child,th:first-child{{text-align:left;font-weight:700}} tr:last-child td{{border-bottom:none}}
    .links{{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}} .button{{display:inline-block;padding:10px 14px;border-radius:10px;border:1px solid var(--line);color:#123d86;background:#fff;text-decoration:none;font-weight:650}} footer{{margin-top:28px;color:var(--muted);font-size:13px}}
    @media(max-width:900px){{.grid,.two-col,.method{{grid-template-columns:1fr}} main{{padding:18px 14px 42px}} header{{padding:32px 18px 26px}} .chart{{height:280px;gap:4px}} .bar{{width:82%}}}}
  </style>
</head>
<body>
  <header><div class="wrap"><h1>Censo Escolar ES: Tempo Integral nos Anos Finais</h1><p class="subtitle">Painel gerado a partir dos microdados do Censo Escolar do INEP. Critério principal: escola no Espírito Santo com pelo menos uma matrícula em tempo integral nos Anos Finais do Ensino Fundamental.</p></div></header>
  <main class="wrap">
    <div class="note"><strong>Status:</strong> dados processados até {ano_final}. {status_2025} A visualização principal começa em 2016, pois 2015 apresenta indício de oferta parcial ou classificação distinta de jornada.</div>

    <div class="grid">
      <div class="card"><div class="kpi-label">Escolas estaduais com AF integral</div><div class="kpi-value">{fmt_int(ultimo['escolas_estaduais_com_af_integral'])}</div><div class="kpi-note">{ano_final}</div></div>
      <div class="card"><div class="kpi-label">Matrículas estaduais AF integral</div><div class="kpi-value">{fmt_int(ultimo['matriculas_estaduais_af_integral'])}</div><div class="kpi-note">{ano_final}</div></div>
      <div class="card"><div class="kpi-label">% das escolas estaduais com AF integral</div><div class="kpi-value">{fmt_pct(ultimo['pct_escolas_estaduais_af_integral'])}</div><div class="kpi-note">{ano_final}</div></div>
      <div class="card"><div class="kpi-label">Crescimento das matrículas integrais</div><div class="kpi-value">{fmt_pct(crescimento_matriculas)}</div><div class="kpi-note">{ano_base} a {ano_final}</div></div>
    </div>

    <section class="card"><h2>Por que o desenho precisa considerar adoção escalonada?</h2><p class="lead">A expansão não ocorreu em um único ano. O estoque de escolas estaduais com Anos Finais em tempo integral cresceu em ondas, sobretudo a partir de 2020. Isso exige comparar escolas conforme o ano em que entraram no modelo.</p><div class="method"><div class="method-step"><span class="step-number">1</span><strong>Entrada em anos diferentes</strong><p class="small">Cada escola tem seu próprio ano de entrada no tempo integral.</p></div><div class="method-step"><span class="step-number">2</span><strong>Comparação com ainda não tratadas</strong><p class="small">Uma escola que ainda não entrou pode servir como comparação naquele ano.</p></div><div class="method-step"><span class="step-number">3</span><strong>Efeitos por coorte</strong><p class="small">Os efeitos são estimados por coorte de entrada e por tempo de exposição.</p></div></div></section>

    <section class="two-col">
      <div class="card"><h2>Estoque de escolas estaduais com AF integral</h2><div class="chart"><div class="axis-note">nº de escolas</div>{gerar_barras_estoque(df_principal, 'escolas_estaduais_com_af_integral', '')}</div><p class="caption">Mostra o estoque anual de escolas estaduais com ao menos uma matrícula integral nos Anos Finais.</p></div>
      <div class="card"><h2>Variação líquida anual no número de escolas</h2><div class="chart"><div class="axis-note">diferença em relação ao ano anterior</div>{gerar_barras_variacao(df_principal, 'var_liquida_escolas_estaduais_af_integral')}</div><p class="caption">Mostra a mudança líquida no estoque. Para identificar coortes reais de entrada, o próximo produto será a base escola-ano.</p></div>
    </section>

    <section class="two-col">
      <div class="card"><h2>Matrículas estaduais AF integral</h2><div class="chart"><div class="axis-note">nº de matrículas</div>{gerar_barras_estoque(df_principal, 'matriculas_estaduais_af_integral', 'green')}</div><p class="caption">Mostra a escala de atendimento em tempo integral nos Anos Finais da rede estadual.</p></div>
      <div class="card"><h2>Tabela para a metodologia</h2><p class="lead">Esta tabela resume o argumento empírico: a expansão foi gradual. Ela ainda não substitui a base escola-ano, mas já sustenta a escolha de um desenho com adoção escalonada.</p><div class="table-wrap">{tabela_metodo}</div></div>
    </section>

    <section class="card"><h2>Tabela-resumo</h2><div class="table-wrap">{tabela_resumo}</div><div class="links"><a class="button" href="../outputs/tabelas/es_af_tempo_integral_2015_2025.csv">Abrir CSV</a><a class="button" href="../outputs/tabelas/es_af_tempo_integral_2015_2025.xlsx">Abrir Excel</a><a class="button" href="https://github.com/EduardoAraujoOx/Educacao">Ver repositório</a><a class="button" href="https://github.com/EduardoAraujoOx/Educacao/actions/workflows/rodar-censo.yml">Atualizar dados</a></div></section>

    <footer>Fonte: microdados do Censo Escolar/INEP, processados por rotina reprodutível em Python. Para avaliação causal, o ano efetivo de entrada de cada escola no programa estadual deve ser validado com registros administrativos da SEDU.</footer>
  </main>
</body>
</html>
"""

    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Site gerado em {DOCS_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
