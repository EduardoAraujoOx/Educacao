"""Gera base escola-ano e tabelas de coortes de entrada.

Este script transforma os microdados anuais do Censo Escolar em uma base
longitudinal escola-ano para o Espírito Santo. O objetivo é sair da tabela
agregada de estoque e construir os insumos da metodologia de adoção escalonada:

1. base escola-ano com código INEP, município, dependência administrativa,
   matrículas nos Anos Finais e matrículas integrais nos Anos Finais;
2. primeiro ano em que cada escola aparece com Anos Finais em tempo integral;
3. tabela de coortes para a rede estadual;
4. tabela de escolas ainda não tratadas em cada ano.

Observação: o primeiro ano observado no Censo não deve ser interpretado
automaticamente como entrada institucional no programa. A classificação final
de tratamento deve ser validada com registros administrativos da SEDU.
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


def ler_csv(zf: zipfile.ZipFile, nome: str) -> pd.DataFrame:
    with zf.open(nome) as f:
        return pd.read_csv(f, sep=";", encoding="latin1", low_memory=False)


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.upper() for c in df.columns]
    return df


def coluna_existente(df: pd.DataFrame, candidatos: list[str], obrigatoria: bool = True) -> str | None:
    for col in candidatos:
        if col in df.columns:
            return col
    if obrigatoria:
        raise KeyError(f"Nenhuma das colunas esperadas existe: {candidatos}")
    return None


def selecionar_escolas(zf: zipfile.ZipFile) -> pd.DataFrame:
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


def agregar_matriculas(zf: zipfile.ZipFile, df_escola: pd.DataFrame) -> pd.DataFrame:
    nome_matricula = localizar_csv(zf, [r"tabela_matricula_\d{4}\.csv$", r"matricula.*\.csv$"])
    logging.info("Arquivo de matrículas localizado: %s", nome_matricula)
    df_mat = normalizar_colunas(ler_csv(zf, nome_matricula))

    col_ent = coluna_existente(df_mat, ["CO_ENTIDADE"])
    col_etapa = coluna_existente(df_mat, ["TP_ETAPA_ENSINO"])
    col_integral = coluna_existente(df_mat, ["IN_TEMPO_INTEGRAL", "IN_INTEGRAL", "IN_MATRICULA_TEMPO_INTEGRAL"])

    df_mat[col_etapa] = pd.to_numeric(df_mat[col_etapa], errors="coerce")
    df_mat[col_integral] = pd.to_numeric(df_mat[col_integral], errors="coerce").fillna(0)
    df_af = df_mat[df_mat[col_etapa].isin(ANOS_FINAIS_CODIGOS)].copy()

    total = df_af.groupby(col_ent).size().rename("QT_MAT_FUND_AF")
    integral = df_af[df_af[col_integral] == 1].groupby(col_ent).size().rename("QT_MAT_FUND_AF_INT")
    agg = pd.concat([total, integral], axis=1).fillna(0).reset_index()

    col_ent_escola = coluna_existente(df_escola, ["CO_ENTIDADE"])
    df = df_escola.merge(agg, left_on=col_ent_escola, right_on=col_ent, how="left")
    df["QT_MAT_FUND_AF"] = pd.to_numeric(df["QT_MAT_FUND_AF"], errors="coerce").fillna(0)
    df["QT_MAT_FUND_AF_INT"] = pd.to_numeric(df["QT_MAT_FUND_AF_INT"], errors="coerce").fillna(0)
    return df


def ler_base_ano(ano: int) -> pd.DataFrame:
    with zipfile.ZipFile(BytesIO(baixar_zip(ano))) as zf:
        df = selecionar_escolas(zf)
        if {"QT_MAT_FUND_AF", "QT_MAT_FUND_AF_INT"}.issubset(set(df.columns)):
            return df
        logging.info("Agregados de matrícula não encontrados. Recalculando por matrícula para %s.", ano)
        return agregar_matriculas(zf, df)


def processar_ano(ano: int) -> pd.DataFrame:
    df = ler_base_ano(ano)

    col_ent = coluna_existente(df, ["CO_ENTIDADE"])
    col_nome = coluna_existente(df, ["NO_ENTIDADE", "NO_ESCOLA"], obrigatoria=False)
    col_uf = coluna_existente(df, ["SG_UF", "CO_UF"])
    col_dep = coluna_existente(df, ["TP_DEPENDENCIA", "TP_DEPENDENCIA_ADM"])
    col_af = coluna_existente(df, ["QT_MAT_FUND_AF"])
    col_af_int = coluna_existente(df, ["QT_MAT_FUND_AF_INT"])
    col_mun = coluna_existente(df, ["NO_MUNICIPIO"], obrigatoria=False)
    col_co_mun = coluna_existente(df, ["CO_MUNICIPIO"], obrigatoria=False)

    if col_uf == "SG_UF":
        df_es = df[df[col_uf].astype(str).str.upper() == "ES"].copy()
    else:
        df_es = df[pd.to_numeric(df[col_uf], errors="coerce") == 32].copy()

    for col in [col_dep, col_af, col_af_int]:
        df_es[col] = pd.to_numeric(df_es[col], errors="coerce").fillna(0)

    out = pd.DataFrame({
        "ano": ano,
        "co_entidade": df_es[col_ent].astype(str),
        "nome_escola": df_es[col_nome].astype(str) if col_nome else "",
        "co_municipio": df_es[col_co_mun] if col_co_mun else pd.NA,
        "municipio": df_es[col_mun].astype(str) if col_mun else "",
        "tp_dependencia": df_es[col_dep].astype(int),
        "qt_mat_fund_af": df_es[col_af].astype(int),
        "qt_mat_fund_af_int": df_es[col_af_int].astype(int),
    })

    out["dependencia"] = out["tp_dependencia"].map({1: "Federal", 2: "Estadual", 3: "Municipal", 4: "Privada"}).fillna("Outra")
    out["tem_af"] = out["qt_mat_fund_af"] > 0
    out["tem_af_integral"] = (out["qt_mat_fund_af"] > 0) & (out["qt_mat_fund_af_int"] > 0)
    out["prop_af_integral"] = out["qt_mat_fund_af_int"] / out["qt_mat_fund_af"].replace({0: pd.NA})
    return out


def construir_painel() -> pd.DataFrame:
    partes = []
    erros = []
    for ano in ANOS:
        try:
            partes.append(processar_ano(ano))
        except Exception as exc:  # noqa: BLE001
            logging.exception("Erro ao processar escola-ano %s", ano)
            erros.append({"ano": ano, "erro": str(exc)})
    if not partes:
        raise RuntimeError("Nenhum ano foi processado para a base escola-ano.")
    painel = pd.concat(partes, ignore_index=True)
    if erros:
        pd.DataFrame(erros).to_csv(OUTPUT_DIR / "erros_escola_ano.csv", index=False, encoding="utf-8-sig")
    return painel


def adicionar_coortes(painel: pd.DataFrame) -> pd.DataFrame:
    painel = painel.copy()
    primeiros = (
        painel[painel["tem_af_integral"]]
        .groupby("co_entidade")["ano"]
        .min()
        .rename("ano_primeiro_af_integral_observado")
        .reset_index()
    )
    painel = painel.merge(primeiros, on="co_entidade", how="left")
    painel["tratada_no_ano"] = painel["tem_af_integral"]
    painel["nunca_tratada_observada"] = painel["ano_primeiro_af_integral_observado"].isna()
    painel["ainda_nao_tratada_no_ano"] = painel["ano_primeiro_af_integral_observado"].isna() | (
        painel["ano"] < painel["ano_primeiro_af_integral_observado"]
    )
    painel["coorte_entrada_observada"] = painel["ano_primeiro_af_integral_observado"]
    return painel


def gerar_tabela_coortes(painel: pd.DataFrame, ano_inicial: int) -> pd.DataFrame:
    p = painel[(painel["ano"] >= ano_inicial) & (painel["tp_dependencia"] == 2) & (painel["tem_af"])].copy()

    # Recalcula a primeira entrada dentro da janela escolhida. Escolas já integrais
    # no primeiro ano da janela são classificadas como estoque inicial, não como
    # nova entrada causal naquele ano.
    primeira = (
        p[p["tem_af_integral"]]
        .groupby("co_entidade")["ano"]
        .min()
        .rename("primeiro_ano_na_janela")
        .reset_index()
    )
    p = p.drop(columns=["primeiro_ano_na_janela"], errors="ignore").merge(primeira, on="co_entidade", how="left")

    linhas = []
    anos = sorted(p["ano"].unique())
    for ano in anos:
        p_ano = p[p["ano"] == ano]
        estoque = int(p_ano["tem_af_integral"].sum())
        novas = int(((p_ano["primeiro_ano_na_janela"] == ano) & (ano > ano_inicial)).sum())
        estoque_inicial = int(((p_ano["primeiro_ano_na_janela"] == ano) & (ano == ano_inicial)).sum())
        ainda_nao = int((p_ano["primeiro_ano_na_janela"].isna() | (p_ano["primeiro_ano_na_janela"] > ano)).sum())
        nunca_ate_fim = int(p_ano["primeiro_ano_na_janela"].isna().sum())
        linhas.append({
            "ano": int(ano),
            "estoque_inicial_no_ano_base": estoque_inicial,
            "novas_escolas_tratadas_observadas": novas,
            "escolas_ainda_nao_tratadas_no_ano": ainda_nao,
            "escolas_nunca_tratadas_ate_fim_da_janela": nunca_ate_fim,
            "estoque_tratado_acumulado": estoque,
            "matriculas_estaduais_af_integral": int(p_ano["qt_mat_fund_af_int"].sum()),
        })
    return pd.DataFrame(linhas)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    painel = adicionar_coortes(construir_painel())

    escola_ano_path = OUTPUT_DIR / "escola_ano_af_tempo_integral_es_2015_2025.csv"
    painel.to_csv(escola_ano_path, index=False, encoding="utf-8-sig")
    painel.to_excel(OUTPUT_DIR / "escola_ano_af_tempo_integral_es_2015_2025.xlsx", index=False)

    coortes_2016 = gerar_tabela_coortes(painel, 2016)
    coortes_2019 = gerar_tabela_coortes(painel, 2019)
    coortes_2016.to_csv(OUTPUT_DIR / "coortes_estaduais_af_tempo_integral_2016_2025.csv", index=False, encoding="utf-8-sig")
    coortes_2019.to_csv(OUTPUT_DIR / "coortes_estaduais_af_tempo_integral_2019_2025.csv", index=False, encoding="utf-8-sig")
    coortes_2016.to_excel(OUTPUT_DIR / "coortes_estaduais_af_tempo_integral_2016_2025.xlsx", index=False)
    coortes_2019.to_excel(OUTPUT_DIR / "coortes_estaduais_af_tempo_integral_2019_2025.xlsx", index=False)

    print(f"Base escola-ano salva em {escola_ano_path}")
    print("Coortes 2016+:")
    print(coortes_2016.to_string(index=False))
    print("Coortes 2019+:")
    print(coortes_2019.to_string(index=False))


if __name__ == "__main__":
    main()
