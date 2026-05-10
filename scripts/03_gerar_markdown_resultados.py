"""Gera uma página Markdown com os resultados processados.

A página é salva em outputs/README.md para facilitar visualização direta
no GitHub após a execução do workflow.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = BASE_DIR / "outputs"
TABELA_PATH = OUTPUTS_DIR / "tabelas" / "es_af_tempo_integral_2015_2025.csv"
README_PATH = OUTPUTS_DIR / "README.md"

COLUNAS_VISUAIS = [
    "ano",
    "escolas_estaduais_com_af",
    "escolas_estaduais_com_af_integral",
    "pct_escolas_estaduais_af_integral",
    "matriculas_estaduais_af",
    "matriculas_estaduais_af_integral",
    "pct_matriculas_estaduais_af_integral",
    "escolas_municipais_com_af_integral",
    "matriculas_municipais_af_integral",
]

RENOMEAR = {
    "ano": "Ano",
    "escolas_estaduais_com_af": "Escolas estaduais com AF",
    "escolas_estaduais_com_af_integral": "Escolas estaduais com AF integral",
    "pct_escolas_estaduais_af_integral": "% escolas estaduais AF integral",
    "matriculas_estaduais_af": "Matrículas estaduais AF",
    "matriculas_estaduais_af_integral": "Matrículas estaduais AF integral",
    "pct_matriculas_estaduais_af_integral": "% matrículas estaduais AF integral",
    "escolas_municipais_com_af_integral": "Escolas municipais AF integral",
    "matriculas_municipais_af_integral": "Matrículas municipais AF integral",
}


def formatar_tabela(df: pd.DataFrame) -> pd.DataFrame:
    tabela = df[COLUNAS_VISUAIS].rename(columns=RENOMEAR).copy()

    colunas_num = [c for c in tabela.columns if c != "Ano"]
    for col in colunas_num:
        if col.startswith("%"):
            tabela[col] = tabela[col].map(lambda x: "" if pd.isna(x) else f"{x:.1f}%".replace(".", ","))
        else:
            tabela[col] = tabela[col].map(lambda x: "" if pd.isna(x) else f"{int(x):,}".replace(",", "."))

    return tabela


def main() -> None:
    if not TABELA_PATH.exists():
        raise FileNotFoundError(
            f"Tabela não encontrada: {TABELA_PATH}. Rode scripts/01_processar_censo_es.py antes."
        )

    df = pd.read_csv(TABELA_PATH)
    tabela_md = formatar_tabela(df).to_markdown(index=False)

    conteudo = f"""# Resultados — Censo ES Tempo Integral

Tabela gerada a partir dos microdados do Censo Escolar do INEP.

Critério principal: escola no Espírito Santo com `QT_MAT_FUND_AF_INT > 0`, isto é, ao menos uma matrícula em tempo integral nos Anos Finais do Ensino Fundamental.

## Tabela-resumo

{tabela_md}

## Arquivos para download

- [CSV completo](tabelas/es_af_tempo_integral_2015_2025.csv)
- [Excel completo](tabelas/es_af_tempo_integral_2015_2025.xlsx)

## Gráficos

### Escolas estaduais com Anos Finais em tempo integral

![Escolas estaduais com Anos Finais em tempo integral](graficos/escolas_estaduais_af_integral.png)

### Matrículas estaduais nos Anos Finais em tempo integral

![Matrículas estaduais nos Anos Finais em tempo integral](graficos/matriculas_estaduais_af_integral.png)

### Percentual de matrículas estaduais dos Anos Finais em tempo integral

![Percentual de matrículas estaduais dos Anos Finais em tempo integral](graficos/pct_matriculas_estaduais_af_integral.png)

## Observação metodológica

O Censo Escolar permite reconstruir a evolução observada da oferta declarada de matrículas em tempo integral nos Anos Finais. Para avaliação causal, o ano efetivo de entrada das escolas no programa estadual deve ser validado com registros administrativos da SEDU.
"""

    README_PATH.write_text(conteudo, encoding="utf-8")
    print(f"Página de resultados salva em {README_PATH}")


if __name__ == "__main__":
    main()
