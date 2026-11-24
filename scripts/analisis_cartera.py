"""
Análisis de cartera de crédito de consumo (datos sintéticos de "CrediAndes").

Calcula:
  1. KPIs mensuales: cartera bruta, ICV 30+, mora 90+, desembolsos y castigos.
  2. Cosechas (vintage): % de créditos que alguna vez llegan a 30+ días por mes en libros.
  3. Matriz de rodamiento (roll rates) de los últimos 6 meses.
  4. PSI (índice de estabilidad poblacional) por variable y canal.
  5. Mora temprana por banda de score y simulación de un punto de corte.

Salida: ../datos/resultados/*.csv  (también sirven como tablas para Power BI)
Uso:    python analisis_cartera.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent / "datos"
RES = BASE / "resultados"
RES.mkdir(exist_ok=True)

VENCIDA = 2      # estado 2 = 31-60 días: desde aquí la cartera es "vencida" (>30 días)
MORA_90 = 4      # estado 4 = 91-120 días
ACTIVOS = range(0, 7)
CAMBIO_ALIADOS = pd.Timestamp("2024-07-01")


def cargar():
    cred = pd.read_csv(BASE / "creditos.csv", parse_dates=["fecha_desembolso"])
    des = pd.read_csv(BASE / "desempeno_mensual.csv", parse_dates=["fecha_corte"])
    des = des.merge(cred[["id_credito", "fecha_desembolso", "canal", "banda_score"]], on="id_credito")
    return cred, des


def kpis_mensuales(cred, des):
    act = des[des["estado_mora"].isin(ACTIVOS)]
    k = act.groupby("fecha_corte").agg(
        cartera_bruta=("saldo_capital", "sum"),
        creditos_activos=("id_credito", "nunique"),
    )
    k["cartera_vencida_30"] = act[act["estado_mora"] >= VENCIDA].groupby("fecha_corte")["saldo_capital"].sum()
    k["cartera_mora_90"] = act[act["estado_mora"] >= MORA_90].groupby("fecha_corte")["saldo_capital"].sum()
    k["castigos"] = des[des["estado_mora"] == 7].groupby("fecha_corte")["saldo_capital"].sum()
    k["desembolsos"] = cred.groupby("fecha_desembolso")["monto_desembolsado"].sum()
    k = k.fillna(0)
    k["icv_30"] = k["cartera_vencida_30"] / k["cartera_bruta"]
    k["mora_90"] = k["cartera_mora_90"] / k["cartera_bruta"]

    por_canal = act.assign(venc=np.where(act["estado_mora"] >= VENCIDA, act["saldo_capital"], 0)) \
        .groupby(["fecha_corte", "canal"])[["saldo_capital", "venc"]].sum()
    por_canal["icv_30"] = por_canal["venc"] / por_canal["saldo_capital"]
    return k.reset_index(), por_canal.reset_index()


def cosechas(des, max_mob=24):
    d = des[des["meses_en_libros"].between(1, max_mob)].copy()
    d["cosecha"] = d["fecha_desembolso"].dt.to_period("Q").astype(str)
    d["en_30"] = d["estado_mora"].between(VENCIDA, 7)
    d = d.sort_values(["id_credito", "meses_en_libros"])
    d["alguna_vez_30"] = d.groupby("id_credito")["en_30"].cummax()
    # Los créditos cerrados (pagados) mantienen su último estado "alguna vez 30+"
    total = des.groupby(["canal"])["id_credito"].nunique()
    filas = []
    for (canal, cosecha), g in d.groupby(["canal", "cosecha"]):
        n_cosecha = g["id_credito"].nunique()
        ultimo_mob = g["meses_en_libros"].max()
        ult = g.pivot_table(index="id_credito", columns="meses_en_libros", values="alguna_vez_30", aggfunc="max")
        ult = ult.reindex(columns=range(1, ultimo_mob + 1)).ffill(axis=1).fillna(False)
        observados = des[(des["canal"] == canal) & (des["fecha_desembolso"].dt.to_period("Q").astype(str) == cosecha)]
        max_obs = observados["meses_en_libros"].max()
        for mob in range(1, min(ultimo_mob, max_obs) + 1):
            filas.append({"canal": canal, "cosecha": cosecha, "mes_en_libros": mob,
                          "creditos": n_cosecha, "pct_alguna_vez_30": ult[mob].astype(bool).mean()})
    return pd.DataFrame(filas)


def roll_rates(des, meses=6):
    d = des[["id_credito", "fecha_corte", "estado_mora"]].sort_values(["id_credito", "fecha_corte"])
    d["estado_sig"] = d.groupby("id_credito")["estado_mora"].shift(-1)
    ultimo = d["fecha_corte"].max()
    desde = ultimo - pd.DateOffset(months=meses)
    d = d[(d["fecha_corte"] >= desde) & (d["fecha_corte"] < ultimo) & d["estado_mora"].isin(ACTIVOS)]
    d = d.dropna(subset=["estado_sig"])
    m = pd.crosstab(d["estado_mora"], d["estado_sig"].astype(int), normalize="index")
    return m


def psi(base, actual, bins=10, categorica=False):
    eps = 1e-4
    if categorica:
        b = base.value_counts(normalize=True)
        a = actual.value_counts(normalize=True).reindex(b.index, fill_value=0)
    else:
        cortes = np.unique(np.quantile(base, np.linspace(0, 1, bins + 1)))
        cortes[0], cortes[-1] = -np.inf, np.inf
        b = pd.cut(base, cortes).value_counts(normalize=True, sort=False)
        a = pd.cut(actual, cortes).value_counts(normalize=True, sort=False)
    b, a = b + eps, a + eps
    return float(((a - b) * np.log(a / b)).sum())


def tabla_psi(cred):
    """Línea base: originaciones 2023. Población actual: ene-jun 2025."""
    base = cred[cred["fecha_desembolso"].dt.year == 2023]
    actual = cred[cred["fecha_desembolso"].between("2025-01-01", "2025-06-30")]
    variables = {"score_originacion": False, "ingreso_mensual": False, "edad": False,
                 "monto_desembolsado": False, "plazo_meses": True}
    filas = []
    for canal in ["Aliados", "Digital", "Oficina"]:
        for var, cat in variables.items():
            filas.append({"canal": canal, "variable": var,
                          "psi": psi(base.loc[base.canal == canal, var], actual.loc[actual.canal == canal, var], categorica=cat)})
    return pd.DataFrame(filas)


def mora_temprana(cred, des):
    """% de créditos que llegan a 30+ días en sus primeros 6 meses (cosechas con 6 meses de maduración)."""
    d = des[des["meses_en_libros"].between(1, 6)]
    marca = d.groupby("id_credito")["estado_mora"].apply(lambda s: s.between(VENCIDA, 7).any()).rename("mora_30_6m")
    c = cred[cred["fecha_desembolso"] <= "2025-06-30"].merge(marca, on="id_credito", how="left").fillna({"mora_30_6m": False})
    c["periodo"] = np.where(c["fecha_desembolso"] >= CAMBIO_ALIADOS, "Desde jul-2024", "Antes de jul-2024")
    por_banda = c.groupby(["canal", "periodo", "banda_score"]).agg(
        creditos=("id_credito", "count"), mora_30_6m=("mora_30_6m", "mean")).reset_index()

    # Simulación: ¿qué pasa si en Aliados se exige un score mínimo?
    ali = c[(c["canal"] == "Aliados") & (c["periodo"] == "Desde jul-2024")]
    sim = []
    for corte in [0, 550, 575, 600, 625, 650]:
        aprob = ali[ali["score_originacion"] >= corte]
        sim.append({"score_minimo": corte if corte else "Sin corte",
                    "pct_volumen_aprobado": len(aprob) / len(ali),
                    "mora_30_6m": aprob["mora_30_6m"].mean(),
                    "creditos_aprobados": len(aprob)})
    referencia = c[(c["canal"] != "Aliados")]["mora_30_6m"].mean()
    return c, por_banda, pd.DataFrame(sim), referencia


if __name__ == "__main__":
    cred, des = cargar()
    k, k_canal = kpis_mensuales(cred, des)
    k.to_csv(RES / "kpis_mensuales.csv", index=False)
    k_canal.to_csv(RES / "icv_por_canal.csv", index=False)
    cosechas(des).to_csv(RES / "cosechas.csv", index=False)
    roll_rates(des).to_csv(RES / "roll_rates.csv")
    tabla_psi(cred).to_csv(RES / "psi.csv", index=False)
    c, por_banda, sim, ref = mora_temprana(cred, des)
    por_banda.to_csv(RES / "mora_temprana_por_banda.csv", index=False)
    sim.assign(referencia_otros_canales=ref).to_csv(RES / "simulacion_corte_score.csv", index=False)

    ult = k.iloc[-1]
    print(f"Corte {ult.fecha_corte:%b-%Y}: cartera {ult.cartera_bruta/1e9:,.1f} mil M COP | "
          f"ICV 30+ {ult.icv_30:.1%} | mora 90+ {ult.mora_90:.1%}")
    print(tabla_psi(cred).pivot(index="variable", columns="canal", values="psi").round(3))
    print(sim.round(3), f"\nreferencia otros canales: {ref:.3f}")
