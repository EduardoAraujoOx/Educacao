"""Processa microdados do Censo Escolar para o Espírito Santo.

Calcula, de 2015 a 2025, o número de escolas com matrículas em tempo
integral nos Anos Finais do Ensino Fundamental, separando redes pública,
estadual e municipal.

A rotina baixa os ZIPs oficiais do INEP, identifica o arquivo de escolas e,
quando necessário, agrega o arquivo de matrículas. Isso acomoda a mudança de
estrutura observada no Censo Escolar 2025.
"""

from __future__ import annotations

import logging
import re
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
import urllib3


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "outputs" / "tabelas"
RAW_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ANOS = list(range(2015, 2026))
ANOS_FINAIS_CODIGOS = {9, 10, 11, 19, 20, 21, 41}

URLS = {
    2015: "https://download.inep.gov.br/microdados/micro_censo_escolar_2015.zip",
    2016: "https://download.inep.gov.br/microdados/micro_censo_escolar_2016.zip",
    2017: "https://download.inep.gov.br/microdados/micro_censo_escolar_2017.zip",
    2018: "https://download.inep.gov.br/microdados/micro_censo_escolar_2018.zip",
    2019: "https://download.inep.gov.br/microdados/micro_censo_escolar_2019.zip",
    2020: "https://download.inep.gov.br/microdados/micro_censo_escolar_2020.zip",
    2021: "https://download.inep.gov.br/microdados/micro_censo_escolar_2021.zip",
    2022: "https://download.inep.gov.br/microdados/micro_censo_escolar_2022.zip",
    2023: "https://download.inep.gov.br/microdados/micro_censo_escolar_2023.zip",
    2024: "https://download.inep.gov.br/microdados/micro_censo_escolar_2024.zip",
    2025: "https://download.inep.gov.br/microdados/micro_censo_escolar_2025.zip",
}

URLS_ALTERNATIVAS = {
    ano: [
        f"https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{ano}.zip",
        f"https://download.inep.gov.br/dados_abertos/microdados/microdados_censo_escolar_{ano}.zip",
        f"https://download.inep.gov.br/microdados/microdados_censo_escolar_{ano}.zip",
    ]
    for ano in ANOS
}
URLS_ALTERNATIVAS[2025].append(
    "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2025_.zip"
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def baixar_zip(ano: int) -> bytes:
    """Baixa ou reutiliza o ZIP do Censo Escolar para um ano."""
    raw_path = RAW_DIR / f"censo_escolar_{ano}.zip"
    if raw_path.exists() and raw_path.stat().st_size > 1_000_000:
        logging.info("Usando arquivo em cache para %s: %s", ano, raw_path)
        return raw_path.read_bytes()

    urls = [URLS[ano], *URLS_ALTERNATIVAS.get(ano, [])]
    ultimo_erro: Exception | None = None

    for url in urls:
        try:
            logging.info("Baixando %s: %s", ano, url)
            resp = requests.get(url, timeout=180, verify=False)
            resp.raise_for_status()
            if len(resp.content) < 1_000_000:
                raise ValueError("arquivo baixado parece pequeno demais")
            raw_path.write_bytes(resp.content)
            return resp.content
        except Exception as exc:  # noqa: BLE001
            ultimo_erro = exc
            logging.warning("Falha no download de %s por %s: %s", ano, url, exc)

    raise RuntimeError(f"Não foi possível baixar o Censo Escolar {ano}") from ultimo_erro


def localizar_csv(zf: zipfile.ZipFile, padroes: list[str]) -> str:
    csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    for padrao in padroes:
        candidatos = [n for n in csvs if re.search(padrao, n.lower())]
        if candidatos:
            return sorted(candidatos, key=len)[0]
    raise ValueError(f"CSV não encontrado para padrões {padroes}. CSVs disponíveis: {csvs[:10]}")


def ler_csv(zf: zipfile.ZipFile, nome: str, usecols: list[str] | None = None) -> pd.DataFrame:
    with zf.open(nome) as f:
        return pd.read_csv(f, sep=";", encoding="latin1", low_memory=False, usecols=usecols)


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.upper() for c in df.columns]
    return df


def coluna_existente(df: pd.DataFrame, candidatos: list[str]) -> str:
    for col in candidatos:
        if col in df.columns:
            return col
    raise KeyError(f"Nenhuma das colunas esperadas existe: {candidatos}")


def selecionar_escolas_agregado(zf: zipfile.ZipFile) -> pd.DataFrame:
    nome = localizar_csv(
        zf,
        [
            r"tabela_escola_\d{4}\.csv$",
            r"microdados_ed_basica.*\.csv$",
            r"microdados_educacao_basica.*\.csv$",
            r"escolas.*\.csv$",
        ],
    )
    logging.info("Arquivo de escolas localizado: %s", nome)
    return normalizar_colunas(ler_csv(zf, nome))


def construir_agregado_por_matricula(zf: zipfile.ZipFile, df_escola: pd.DataFrame) -> pd.DataFrame:
    """Reconstrói QT_MAT_FUND_AF e QT_MAT_FUND_AF_INT a partir da tabela de matrículas."""
    nome_matricula = localizar_csv(zf, [r"tabela_matricula_\d{4}\.csv$", r"matricula.*\.csv$"])
    logging.info("Arquivo de matrículas localizado: %s", nome_matricula)
    df_mat = normalizar_colunas(ler_csv(zf, nome_matricula))

    col_ent = coluna_existente(df_mat, ["CO_ENTIDADE"])
    col_etapa = coluna_existente(df_mat, ["TP_ETAPA_ENSINO"])
    col_integral = coluna_existente(df_mat, ["IN_TEMPO_INTEGRAL", "IN_INTEGRAL", "IN_MATRICULA_TEMPO_INTEGRAL"])

    df_mat[col_etapa] = pd.to_numeric(df_mat[col_etapa], errors="coerce")
    df_mat[col_integral] = pd.to_numeric(df_mat[col_integral], errors="coerce").fillna(0)

    df_af = df_mat[df_mat[col_etapa].isin(ANOS_FINAIS_CODIGOS)].copy()
    if df_af.empty:
        raise ValueError("Nenhuma matrícula de Anos Finais encontrada pelos códigos configurados.")

    total = df_af.groupby(col_ent).size().rename("QT_MAT_FUND_AF")
    integral = df_af[df_af[col_integral] == 1].groupby(col_ent).size().rename("QT_MAT_FUND_AF_INT")
    agg = pd.concat([total, integral], axis=1).fillna(0).reset_index()

    col_ent_escola = coluna_existente(df_escola, ["CO_ENTIDADE"])
    df = df_escola.merge(agg, left_on=col_ent_escola, right_on=col_ent, how="left")
    df["QT_MAT_FUND_AF"] = pd.to_numeric(df["QT_MAT_FUND_AF"], errors="coerce").fillna(0)
    df["QT_MAT_FUND_AF_INT"] = pd.to_numeric(df["QT_MAT_FUND_AF_INT"], errors="coerce").fillna(0)
    return df


def ler_base_ano(zip_bytes: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        df = selecionar_escolas_agregado(zf)
        cols = set(df.columns)
        if {"QT_MAT_FUND_AF", "QT_MAT_FUND_AF_INT"}.issubset(cols):
            return df
        logging.info("Arquivo de escolas não contém agregados de matrícula. Recalculando por Tabela_Matricula.")
        return construir_agregado_por_matricula(zf, df)


def processar_ano(ano: int) -> dict[str, int | float]:
    df = ler_base_ano(baixar_zip(ano))

    col_uf = coluna_existente(df, ["SG_UF", "CO_UF"])
    col_dep = coluna_existente(df, ["TP_DEPENDENCIA", "TP_DEPENDENCIA_ADM"])
    col_af = coluna_existente(df, ["QT_MAT_FUND_AF"])
    col_af_int = coluna_existente(df, ["QT_MAT_FUND_AF_INT"])

    if col_uf == "SG_UF":
        df_es = df[df[col_uf].astype(str).str.upper() == "ES"].copy()
    else:
        df_es = df[pd.to_numeric(df[col_uf], errors="coerce") == 32].copy()

    for col in [col_dep, col_af, col_af_int]:
        df_es[col] = pd.to_numeric(df_es[col], errors="coerce").fillna(0)

    tem_af = df_es[col_af] > 0
    tem_af_integral = df_es[col_af_int] > 0
    publicas = df_es[col_dep].isin([1, 2, 3])
    estaduais = df_es[col_dep] == 2
    municipais = df_es[col_dep] == 3

    # Critério alternativo, mais próximo do indicador de meta: ao menos 25% das
    # matrículas dos Anos Finais em tempo integral. Útil para diagnosticar anos
    # com muitas escolas e poucas matrículas integrais.
    prop_int = df_es[col_af_int] / df_es[col_af].replace({0: pd.NA})
    criterio_25 = prop_int >= 0.25

    return {
        "ano": ano,
        "escolas_publicas_com_af": int((publicas & tem_af).sum()),
        "escolas_publicas_com_af_integral": int((publicas & tem_af & tem_af_integral).sum()),
        "escolas_estaduais_com_af": int((estaduais & tem_af).sum()),
        "escolas_estaduais_com_af_integral": int((estaduais & tem_af & tem_af_integral).sum()),
        "escolas_estaduais_com_af_integral_25pct": int((estaduais & tem_af & criterio_25).sum()),
        "escolas_municipais_com_af": int((municipais & tem_af).sum()),
        "escolas_municipais_com_af_integral": int((municipais & tem_af & tem_af_integral).sum()),
        "matriculas_publicas_af": int(df_es.loc[publicas & tem_af, col_af].sum()),
        "matriculas_publicas_af_integral": int(df_es.loc[publicas & tem_af, col_af_int].sum()),
        "matriculas_estaduais_af": int(df_es.loc[estaduais & tem_af, col_af].sum()),
        "matriculas_estaduais_af_integral": int(df_es.loc[estaduais & tem_af, col_af_int].sum()),
        "matriculas_municipais_af": int(df_es.loc[municipais & tem_af, col_af].sum()),
        "matriculas_municipais_af_integral": int(df_es.loc[municipais & tem_af, col_af_int].sum()),
    }


def adicionar_percentuais(tabela: pd.DataFrame) -> pd.DataFrame:
    tabela = tabela.copy()

    def pct(num: str, den: str) -> pd.Series:
        return (tabela[num] / tabela[den].replace({0: pd.NA}) * 100).round(1)

    tabela["pct_escolas_publicas_af_integral"] = pct("escolas_publicas_com_af_integral", "escolas_publicas_com_af")
    tabela["pct_escolas_estaduais_af_integral"] = pct("escolas_estaduais_com_af_integral", "escolas_estaduais_com_af")
    tabela["pct_escolas_estaduais_af_integral_25pct"] = pct("escolas_estaduais_com_af_integral_25pct", "escolas_estaduais_com_af")
    tabela["pct_escolas_municipais_af_integral"] = pct("escolas_municipais_com_af_integral", "escolas_municipais_com_af")
    tabela["pct_matriculas_estaduais_af_integral"] = pct("matriculas_estaduais_af_integral", "matriculas_estaduais_af")
    tabela["pct_matriculas_municipais_af_integral"] = pct("matriculas_municipais_af_integral", "matriculas_municipais_af")
    tabela["var_liquida_escolas_estaduais_af_integral"] = tabela["escolas_estaduais_com_af_integral"].diff()
    tabela["var_liquida_matriculas_estaduais_af_integral"] = tabela["matriculas_estaduais_af_integral"].diff()
    return tabela


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    resultados = []
    erros = []

    for ano in ANOS:
        try:
            resultados.append(processar_ano(ano))
        except Exception as exc:  # noqa: BLE001
            logging.exception("Erro ao processar %s", ano)
            erros.append({"ano": ano, "erro": str(exc)})

    if not resultados:
        raise RuntimeError("Nenhum ano foi processado com sucesso.")

    tabela = adicionar_percentuais(pd.DataFrame(resultados).sort_values("ano"))

    csv_path = OUTPUT_DIR / "es_af_tempo_integral_2015_2025.csv"
    xlsx_path = OUTPUT_DIR / "es_af_tempo_integral_2015_2025.xlsx"
    tabela.to_csv(csv_path, index=False, encoding="utf-8-sig")
    tabela.to_excel(xlsx_path, index=False)

    if erros:
        pd.DataFrame(erros).to_csv(OUTPUT_DIR / "erros_processamento.csv", index=False, encoding="utf-8-sig")
    else:
        erro_path = OUTPUT_DIR / "erros_processamento.csv"
        if erro_path.exists():
            erro_path.unlink()

    logging.info("Tabela salva em %s", csv_path)
    logging.info("Tabela salva em %s", xlsx_path)
    print(tabela.to_string(index=False))


if __name__ == "__main__":
    main()
