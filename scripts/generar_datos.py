"""
Genera datos SINTÉTICOS de una fintech ficticia ("CrediAndes", empresa inventada)
para el caso de portafolio de análisis de cartera.

Ningún dato proviene de una empresa real. Todo se simula con una cadena de Markov
de días de mora, cuya probabilidad de deterioro depende del score de originación.

Historia incluida en los datos (lo que el análisis debe descubrir):
  - Desde julio de 2024 el canal "Aliados" incorporó un nuevo aliado comercial que
    trae clientes con score más bajo y menores ingresos (cambio de población).
  - Esas cosechas se deterioran más rápido que las anteriores.

Salida (carpeta ../datos):
  creditos.csv            una fila por crédito (datos de originación)
  desempeno_mensual.csv   una fila por crédito y mes de corte (saldo y mora)

Uso:  python generar_datos.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEMILLA = 2026
rng = np.random.default_rng(SEMILLA)
SALIDA = Path(__file__).resolve().parent.parent / "datos"
SALIDA.mkdir(exist_ok=True)

MESES_ORIGINACION = pd.period_range("2023-01", "2025-12", freq="M")
MESES_CORTE = pd.period_range("2023-01", "2025-12", freq="M")
CAMBIO_ALIADOS = pd.Period("2024-07", freq="M")

CANALES = ["Digital", "Aliados", "Oficina"]
PESO_CANALES = [0.50, 0.30, 0.20]
PRODUCTOS = ["Libre inversión", "Microcrédito", "Compra de cartera"]
PESO_PRODUCTOS = [0.55, 0.30, 0.15]
CIUDADES = ["Bogotá", "Medellín", "Cali", "Barranquilla", "Bucaramanga", "Otras"]
PESO_CIUDADES = [0.36, 0.18, 0.13, 0.10, 0.07, 0.16]
PLAZOS = np.array([6, 12, 18, 24, 36])
PESO_PLAZOS = [0.10, 0.35, 0.25, 0.20, 0.10]

# Estados de mora: 0 al día, 1 = 1-30, 2 = 31-60, 3 = 61-90, 4 = 91-120,
# 5 = 121-150, 6 = 151-180, 7 = castigado, 8 = pagado (cerrado)
ETIQUETAS = {0: "Al día", 1: "1-30", 2: "31-60", 3: "61-90", 4: "91-120",
             5: "121-150", 6: "151-180", 7: "Castigado", 8: "Pagado"}


def generar_creditos() -> pd.DataFrame:
    filas = []
    for i, mes in enumerate(MESES_ORIGINACION):
        n = int(400 + i * 15 + rng.normal(0, 20))  # el negocio crece mes a mes
        canal = rng.choice(CANALES, n, p=PESO_CANALES)
        score = rng.normal(655, 70, n)
        ingreso = rng.lognormal(np.log(3_200_000), 0.45, n)
        edad = rng.normal(37, 10, n)

        # Nuevo aliado: población más riesgosa desde julio de 2024
        nuevo = (canal == "Aliados") & (mes >= CAMBIO_ALIADOS)
        score[nuevo] = rng.normal(590, 75, nuevo.sum())
        ingreso[nuevo] = rng.lognormal(np.log(2_300_000), 0.40, nuevo.sum())
        edad[nuevo] = rng.normal(29, 7, nuevo.sum())

        score = np.clip(score, 350, 950).round()
        edad = np.clip(edad, 18, 75).round()
        ingreso = (np.clip(ingreso, 1_300_000, 25_000_000) / 10_000).round() * 10_000
        plazo = rng.choice(PLAZOS, n, p=PESO_PLAZOS)
        monto = np.clip(ingreso * rng.uniform(0.8, 3.5, n), 500_000, 30_000_000)
        monto = (monto / 50_000).round() * 50_000
        tasa_ea = np.clip(0.42 - (score - 650) / 2000 + rng.normal(0, 0.02, n), 0.18, 0.55)

        filas.append(pd.DataFrame({
            "fecha_desembolso": mes.to_timestamp(),
            "canal": canal,
            "producto": rng.choice(PRODUCTOS, n, p=PESO_PRODUCTOS),
            "ciudad": rng.choice(CIUDADES, n, p=PESO_CIUDADES),
            "score_originacion": score.astype(int),
            "ingreso_mensual": ingreso.astype(int),
            "edad": edad.astype(int),
            "monto_desembolsado": monto.astype(int),
            "plazo_meses": plazo,
            "tasa_ea": tasa_ea.round(4),
            "_nuevo_aliado": nuevo,
        }))
    df = pd.concat(filas, ignore_index=True)
    df.insert(0, "id_credito", [f"CR{i:06d}" for i in range(1, len(df) + 1)])
    df["banda_score"] = pd.cut(df["score_originacion"], [0, 550, 600, 650, 700, 750, 2000],
                               labels=["<550", "550-599", "600-649", "650-699", "700-749", "750+"],
                               right=False).astype(str)
    return df


def simular_desempeno(cred: pd.DataFrame) -> pd.DataFrame:
    n = len(cred)
    score = cred["score_originacion"].to_numpy()
    # Probabilidad mensual de pasar de "al día" a "1-30" según el score
    p_entrada = 0.010 + 0.11 / (1 + np.exp((score - 590) / 45))
    p_entrada = np.where(cred["_nuevo_aliado"], p_entrada * 1.35, p_entrada)
    tasa_m = (1 + cred["tasa_ea"].to_numpy()) ** (1 / 12) - 1
    plazo = cred["plazo_meses"].to_numpy()
    monto = cred["monto_desembolsado"].to_numpy().astype(float)
    cuota = monto * tasa_m / (1 - (1 + tasa_m) ** -plazo)
    mes_ini = cred["fecha_desembolso"].dt.to_period("M").map(lambda p: p.ordinal).to_numpy()

    estado = np.full(n, -1)          # -1 = aún no desembolsado
    saldo = monto.copy()
    cuotas_pagadas = np.zeros(n, dtype=int)
    registros = []

    for corte in MESES_CORTE:
        o = corte.ordinal
        nuevos = mes_ini == o
        estado[nuevos] = 0
        vivos = (mes_ini < o) & (estado >= 0) & (estado <= 6)
        u = rng.random(n)
        e = estado.copy()

        # Al día: puede deteriorarse o prepagar
        m0 = vivos & (estado == 0)
        e[m0 & (u < p_entrada)] = 1
        e[m0 & (u >= p_entrada) & (u < p_entrada + 0.012)] = 8   # prepago
        # 1-30: se cura, se queda o empeora
        m1 = vivos & (estado == 1)
        e[m1 & (u < 0.50)] = 0
        e[m1 & (u >= 0.50) & (u < 0.70)] = 1
        e[m1 & (u >= 0.70)] = 2
        # 31-60
        m2 = vivos & (estado == 2)
        e[m2 & (u < 0.22)] = 0
        e[m2 & (u >= 0.22) & (u < 0.38)] = 2
        e[m2 & (u >= 0.38)] = 3
        # 61-90 en adelante: casi siempre rueda
        for s in (3, 4, 5):
            ms = vivos & (estado == s)
            e[ms & (u < 0.08)] = 0
            e[ms & (u >= 0.08) & (u < 0.16)] = s
            e[ms & (u >= 0.16)] = s + 1
        e[vivos & (estado == 6)] = 7                                # castigo a 180+

        # Pago de cuota y amortización (solo quien queda al día)
        paga = vivos & (e == 0)
        interes = saldo * tasa_m
        saldo = np.where(paga, np.maximum(saldo - (cuota - interes), 0), saldo)
        cuotas_pagadas = cuotas_pagadas + paga
        termina = paga & (cuotas_pagadas >= plazo)
        e[termina] = 8
        saldo = np.where(e == 8, 0, saldo)
        estado = np.where(vivos, e, estado)

        en_libros = (mes_ini <= o) & (estado >= 0)
        recien_cerrado = en_libros & np.isin(estado, [7, 8]) & vivos
        mostrar = en_libros & ((estado <= 6) | recien_cerrado)
        idx = np.flatnonzero(mostrar)
        registros.append(pd.DataFrame({
            "id_credito": cred["id_credito"].to_numpy()[idx],
            "fecha_corte": corte.to_timestamp(),
            "meses_en_libros": o - mes_ini[idx],
            "estado_mora": estado[idx],
            "saldo_capital": np.where(estado[idx] == 7, saldo[idx], np.where(estado[idx] == 8, 0, saldo[idx])).round(0).astype(np.int64),
        }))

    des = pd.concat(registros, ignore_index=True)
    des["rango_mora"] = des["estado_mora"].map(ETIQUETAS)
    return des


if __name__ == "__main__":
    creditos = generar_creditos()
    desempeno = simular_desempeno(creditos)
    creditos.drop(columns="_nuevo_aliado").to_csv(SALIDA / "creditos.csv", index=False, encoding="utf-8")
    desempeno.to_csv(SALIDA / "desempeno_mensual.csv", index=False, encoding="utf-8")
    print(f"creditos.csv: {len(creditos):,} filas")
    print(f"desempeno_mensual.csv: {len(desempeno):,} filas")
