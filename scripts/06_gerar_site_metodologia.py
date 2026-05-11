"""Gera página HTML específica para a metodologia de adoção escalonada.

A página usa as tabelas de coortes criadas por `05_gerar_base_escola_ano.py`.
Ela foi pensada para apoiar a proposta de pesquisa, mostrando com dados reais
por que o desenho exige diferenças-em-diferenças com adoção escalonada.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = BASE_DIR / "docs"
TABELAS_DIR = BASE_DIR / "outputs" / "tabelas"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

COORTES_2019 = TABELAS_DIR / "coortes_estaduais_af_tempo_integral_2019_2025.csv"
COORTES_2016 = TABELAS_DIR / "coortes_estaduais_af_tempo_integral_2016_2025.csv"
ESCOLA_ANO = TABELAS_DIR / "escola_ano_af_tempo_integral_es_2015_2025.csv"


def fmt_int(x) -> str:
    if pd.isna(x):
        return ""
    return f"{int(round(float(x))):,}".replace(",", ".")


def fmt_signed(x) -> str:
    if pd.isna(x):
        return ""
    val = int(round(float(x)))
    return f"{val:+,}".replace(",", ".")


def bar_height(value: float, max_value: float, min_height: int = 4) -> int:
    if pd.isna(value) or max_value <= 0:
        return min_height
    return max(min_height, int(round(float(value) / max_value * 100)))


def gerar_barras(df: pd.DataFrame, coluna: str, classe: str = "blue", signed: bool = False) -> str:
    vals = df[coluna].dropna().abs() if signed else df[coluna].dropna()
    max_v = vals.max() if not vals.empty else 1
    partes = []
    for _, row in df.iterrows():
        valor = row[coluna]
        h = bar_height(abs(valor) if signed else valor, max_v)
        rotulo = fmt_signed(valor) if signed else fmt_int(valor)
        partes.append(
            f'<div class="bar-wrap"><div class="bar-label">{rotulo}</div>'
            f'<div class="bar {classe}" style="height:{h}%"></div>'
            f'<div class="bar-year">{int(row["ano"])}</div></div>'
        )
    return "\n".join(partes)


def tabela_html(df: pd.DataFrame, colunas: list[tuple[str, str, str]]) -> str:
    thead = "".join(f"<th>{titulo}</th>" for _, titulo, _ in colunas)
    linhas = []
    for _, row in df.iterrows():
        cells = []
        for col, _, tipo in colunas:
            valor = fmt_signed(row[col]) if tipo == "signed" else fmt_int(row[col])
            cells.append(f"<td>{valor}</td>")
        linhas.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(linhas)}</tbody></table>"


def atualizar_index_com_link() -> None:
    index_path = DOCS_DIR / "index.html"
    if not index_path.exists():
        return
    html = index_path.read_text(encoding="utf-8")
    if "metodologia.html" in html:
        return
    alvo = '<a class="button" href="https://github.com/EduardoAraujoOx/Educacao">Ver repositório</a>'
    novo = alvo + '<a class="button" href="metodologia.html">Ver metodologia escalonada</a>'
    if alvo in html:
        html = html.replace(alvo, novo)
    else:
        html = html.replace("</main>", '<p><a class="button" href="metodologia.html">Ver metodologia escalonada</a></p></main>')
    index_path.write_text(html, encoding="utf-8")


def main() -> None:
    if not COORTES_2019.exists():
        raise FileNotFoundError(f"Tabela de coortes não encontrada: {COORTES_2019}")

    df19 = pd.read_csv(COORTES_2019).sort_values("ano")
    df16 = pd.read_csv(COORTES_2016).sort_values("ano") if COORTES_2016.exists() else df19

    ultimo = df19.iloc[-1]
    total_novas_2019 = df19["novas_escolas_tratadas_observadas"].sum()
    estoque_final = ultimo["estoque_tratado_acumulado"]
    ainda_final = ultimo["escolas_ainda_nao_tratadas_no_ano"]

    tabela_2019 = tabela_html(
        df19,
        [
            ("ano", "Ano", "int"),
            ("novas_escolas_tratadas_observadas", "Novas escolas observadas", "int"),
            ("escolas_ainda_nao_tratadas_no_ano", "Ainda não tratadas", "int"),
            ("estoque_tratado_acumulado", "Estoque tratado", "int"),
            ("matriculas_estaduais_af_integral", "Matrículas integrais", "int"),
        ],
    )
    tabela_2016 = tabela_html(
        df16,
        [
            ("ano", "Ano", "int"),
            ("estoque_inicial_no_ano_base", "Estoque inicial", "int"),
            ("novas_escolas_tratadas_observadas", "Novas escolas", "int"),
            ("escolas_ainda_nao_tratadas_no_ano", "Ainda não tratadas", "int"),
            ("estoque_tratado_acumulado", "Estoque tratado", "int"),
        ],
    )

    escola_ano_link = "../outputs/tabelas/escola_ano_af_tempo_integral_es_2015_2025.csv"
    if not ESCOLA_ANO.exists():
        escola_ano_link = "https://github.com/EduardoAraujoOx/Educacao/tree/main/outputs/tabelas"

    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Metodologia | Adoção escalonada no tempo integral</title>
  <style>
    :root{{--bg:#f6f8fb;--card:#fff;--ink:#172033;--muted:#637083;--line:#d9e1ec;--blue:#1f5fbf;--green:#16805d;--purple:#6b4bb8;--soft:#eef4ff;--cream:#fff8e8}}
    *{{box-sizing:border-box}} body{{margin:0;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.45}}
    header{{background:linear-gradient(135deg,#10233f 0%,#3154a3 100%);color:#fff;padding:42px 24px 34px}} .wrap{{max-width:1180px;margin:0 auto}}
    h1{{margin:0 0 10px;font-size:clamp(28px,4vw,42px);letter-spacing:-.02em}} .subtitle{{margin:0;max-width:920px;color:#dbe8ff;font-size:17px}}
    main{{padding:26px 24px 52px}} section{{margin-top:22px}} .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:22px 0}} .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
    .card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 8px 20px rgba(31,44,71,.06)}} .note{{background:var(--cream);border:1px solid #f0d392;border-radius:14px;padding:14px 16px;color:#543700}}
    .kpi-label{{color:var(--muted);font-size:13px;margin-bottom:8px}} .kpi-value{{font-size:28px;font-weight:760;letter-spacing:-.02em}} .kpi-note{{margin-top:6px;color:var(--muted);font-size:12px}}
    h2{{font-size:22px;margin:0 0 12px;letter-spacing:-.01em}} .lead{{color:var(--muted);margin:0 0 14px}} .caption{{color:var(--muted);font-size:13px;margin-top:10px}}
    .chart{{height:320px;display:flex;align-items:flex-end;gap:8px;border-left:1px solid var(--line);border-bottom:1px solid var(--line);padding:12px 10px 32px;position:relative}} .axis-note{{position:absolute;top:8px;left:12px;font-size:12px;color:var(--muted)}} .bar-wrap{{height:100%;flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:6px}} .bar{{width:70%;border-radius:7px 7px 0 0;background:var(--blue);min-height:2px}} .bar.green{{background:var(--green)}} .bar.purple{{background:var(--purple)}} .bar-label{{font-size:11px;color:var(--ink);font-weight:700}} .bar-year{{font-size:11px;color:var(--muted)}}
    .table-wrap{{overflow-x:auto;border-radius:14px;border:1px solid var(--line);background:#fff}} table{{border-collapse:collapse;width:100%;min-width:900px;font-size:14px}} th,td{{padding:11px 12px;border-bottom:1px solid #e9eef5;text-align:right}} th{{background:#eef3fa;color:#24324c;font-size:12px;text-transform:uppercase;letter-spacing:.03em}} td:first-child,th:first-child{{text-align:left;font-weight:700}} tr:last-child td{{border-bottom:none}}
    .flow{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}} .step{{background:#f9fbff;border:1px solid var(--line);border-radius:14px;padding:14px}} .step strong{{display:block;margin-bottom:6px}} .step span{{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:50%;background:#183f8c;color:#fff;font-weight:800;margin-right:6px}}
    .links{{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}} .button{{display:inline-block;padding:10px 14px;border-radius:10px;border:1px solid var(--line);color:#123d86;background:#fff;text-decoration:none;font-weight:650}} footer{{margin-top:28px;color:var(--muted);font-size:13px}}
    @media(max-width:900px){{.grid,.two-col,.flow{{grid-template-columns:1fr}} main{{padding:18px 14px 42px}} header{{padding:32px 18px 26px}} .chart{{height:280px;gap:4px}} .bar{{width:82%}}}}
  </style>
</head>
<body>
  <header><div class="wrap"><h1>Metodologia: adoção escalonada do tempo integral</h1><p class="subtitle">Página gerada a partir da base escola-ano do Censo Escolar. O objetivo é ilustrar, com dados reais, por que a avaliação deve tratar escolas que entram no tempo integral em anos diferentes.</p></div></header>
  <main class="wrap">
    <div class="note"><strong>Janela principal:</strong> a tabela de coortes abaixo usa 2019 em diante, para evitar que 2015 contamine a leitura com formas possivelmente parciais de jornada ampliada. A base completa preserva 2015 a 2025 para auditoria.</div>

    <div class="grid">
      <div class="card"><div class="kpi-label">Novas escolas observadas na janela</div><div class="kpi-value">{fmt_int(total_novas_2019)}</div><div class="kpi-note">2019 em diante, exclui estoque inicial</div></div>
      <div class="card"><div class="kpi-label">Estoque tratado no último ano</div><div class="kpi-value">{fmt_int(estoque_final)}</div><div class="kpi-note">escolas estaduais com AF integral</div></div>
      <div class="card"><div class="kpi-label">Ainda não tratadas no último ano</div><div class="kpi-value">{fmt_int(ainda_final)}</div><div class="kpi-note">potencial grupo de comparação</div></div>
    </div>

    <section class="card"><h2>Lógica da identificação</h2><p class="lead">A tabela de coortes transforma o estoque anual em uma estrutura compatível com diferenças-em-diferenças com adoção escalonada.</p><div class="flow"><div class="step"><strong><span>1</span>Escola-ano</strong>Identifica, para cada escola e ano, se havia Anos Finais e matrícula integral.</div><div class="step"><strong><span>2</span>Ano de entrada</strong>Marca o primeiro ano em que a escola aparece como integral nos Anos Finais.</div><div class="step"><strong><span>3</span>Coorte</strong>Agrupa escolas pelo ano de entrada observado.</div><div class="step"><strong><span>4</span>Comparação</strong>Em cada ano, compara tratadas com escolas ainda não tratadas.</div></div></section>

    <section class="two-col">
      <div class="card"><h2>Novas escolas tratadas observadas por ano</h2><div class="chart"><div class="axis-note">nº de novas escolas</div>{gerar_barras(df19, 'novas_escolas_tratadas_observadas', 'blue')}</div><p class="caption">Este é o gráfico mais diretamente ligado ao método escalonado. Ele mostra as coortes de entrada observadas na janela principal.</p></div>
      <div class="card"><h2>Escolas ainda não tratadas por ano</h2><div class="chart"><div class="axis-note">potenciais comparações</div>{gerar_barras(df19, 'escolas_ainda_nao_tratadas_no_ano', 'purple')}</div><p class="caption">Mostra quantas escolas ainda poderiam compor o grupo de comparação em cada ano da janela.</p></div>
    </section>

    <section class="card"><h2>Tabela de coortes para a metodologia</h2><p class="lead">Use esta tabela na proposta para mostrar a estrutura empírica do desenho. Ela resume novas escolas observadas, escolas ainda não tratadas, estoque acumulado e matrículas integrais.</p><div class="table-wrap">{tabela_2019}</div></section>

    <section class="card"><h2>Janela alternativa a partir de 2016</h2><p class="lead">Esta tabela preserva uma janela mais longa para diagnóstico. A janela principal recomendada para a interpretação metodológica continua sendo 2019 em diante.</p><div class="table-wrap">{tabela_2016}</div></section>

    <section class="card"><h2>Arquivos gerados</h2><div class="links"><a class="button" href="{escola_ano_link}">Base escola-ano</a><a class="button" href="../outputs/tabelas/coortes_estaduais_af_tempo_integral_2019_2025.csv">Coortes 2019+</a><a class="button" href="../outputs/tabelas/coortes_estaduais_af_tempo_integral_2016_2025.csv">Coortes 2016+</a><a class="button" href="index.html">Voltar ao painel principal</a><a class="button" href="https://github.com/EduardoAraujoOx/Educacao/actions/workflows/rodar-censo.yml">Atualizar dados</a></div></section>

    <footer>Fonte: microdados do Censo Escolar/INEP. A entrada observada no Censo Escolar deve ser validada com registros administrativos da SEDU antes de ser usada como tratamento definitivo em avaliação causal.</footer>
  </main>
</body>
</html>
"""

    (DOCS_DIR / "metodologia.html").write_text(html, encoding="utf-8")
    atualizar_index_com_link()
    print(f"Página de metodologia gerada em {DOCS_DIR / 'metodologia.html'}")


if __name__ == "__main__":
    main()
