"""
Genera las imágenes del caso de portafolio (1920x1200 px) a partir de ../datos/resultados.
Uso: python graficos.py   (ejecutar antes analisis_cartera.py)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

RAIZ = Path(__file__).resolve().parent.parent
RES = RAIZ / "datos" / "resultados"
IMG = RAIZ / "imagenes"
IMG.mkdir(exist_ok=True)

# Paleta y tinta (paleta categórica validada, modo claro)
SUP, PLANO = "#fcfcfb", "#f9f9f7"
TXT1, TXT2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, EJE = "#e1e0d9", "#c3c2b7"
AZUL, NARANJA, AGUA = "#2a78d6", "#eb6834", "#1baf7a"
GRIS_SERIE = "#c3c2b7"
COLOR_CANAL = {"Digital": AZUL, "Aliados": NARANJA, "Oficina": AGUA}
OK, ALERTA, CRITICO = "#0ca30c", "#fab219", "#d03b3b"
AZULES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "font.family": "Segoe UI", "font.size": 13, "text.color": TXT1,
    "axes.edgecolor": EJE, "axes.labelcolor": TXT2, "axes.facecolor": SUP,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 12, "ytick.labelsize": 12,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": SUP,
})
AUTOR = "Anderson Barrero · Analista BI y Riesgo de Crédito"
NOTA = "Datos sintéticos de una fintech ficticia (CrediAndes), generados con Python para fines demostrativos."
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def pct(x, d=1):
    return f"{x * 100:.{d}f}".replace(".", ",") + " %"


def mes_txt(f):
    return f"{MESES[f.month - 1]}-{f.year}"


def lienzo(titulo, subtitulo, seccion):
    fig = plt.figure(figsize=(12, 7.5), dpi=160)
    fig.text(0.05, 0.945, seccion.upper(), fontsize=11, color=MUTED, weight="semibold")
    fig.text(0.05, 0.895, titulo, fontsize=24, weight="semibold", color=TXT1)
    fig.text(0.05, 0.855, subtitulo, fontsize=13.5, color=TXT2)
    fig.add_artist(plt.Line2D([0.05, 0.95], [0.065, 0.065], color=GRID, lw=1))
    fig.text(0.05, 0.035, AUTOR, fontsize=10.5, color=TXT2, weight="semibold")
    fig.text(0.95, 0.035, NOTA, fontsize=9.5, color=MUTED, ha="right")
    return fig


def ejes_limpios(ax, grid_y=True):
    ax.grid(axis="y" if grid_y else "x", color=GRID, lw=1)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    for s in ("left",) if grid_y else ("bottom",):
        ax.spines[s].set_visible(False)


def tarjeta(fig, x, y, w, h, etiqueta, valor, nota=None, color_nota=TXT2):
    fig.add_artist(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.012",
                                  transform=fig.transFigure, fc=PLANO, ec=GRID, lw=1))
    fig.text(x + 0.018, y + h - 0.045, etiqueta, fontsize=12, color=TXT2)
    fig.text(x + 0.018, y + h - 0.115, valor, fontsize=28, weight="semibold", color=TXT1)
    if nota:
        fig.text(x + 0.018, y + 0.025, nota, fontsize=11, color=color_nota)


# ---------------------------------------------------------------- 1. Resumen
def resumen():
    k = pd.read_csv(RES / "kpis_mensuales.csv", parse_dates=["fecha_corte"])
    c = pd.read_csv(RES / "icv_por_canal.csv", parse_dates=["fecha_corte"])
    ult, hace12 = k.iloc[-1], k.iloc[-13]
    fig = lienzo("La cartera crece, pero la mora crece más rápido",
                 f"Indicadores de cartera de consumo al corte de {mes_txt(ult.fecha_corte)}",
                 "Caso de estudio · Analítica de cartera")
    crec = ult.cartera_bruta / hace12.cartera_bruta - 1
    d_icv = (ult.icv_30 - hace12.icv_30) * 100
    d_m90 = (ult.mora_90 - hace12.mora_90) * 100
    tarjetas = [
        ("Cartera bruta", f"$ {ult.cartera_bruta / 1e9:,.1f} mil M".replace(".", ","), f"▲ {pct(crec, 0)} vs. {mes_txt(hace12.fecha_corte)}", TXT2),
        ("ICV 30+ (cartera vencida)", pct(ult.icv_30), f"▲ {d_icv:+.1f}".replace(".", ",") + f" pp vs. {mes_txt(hace12.fecha_corte)}", CRITICO),
        ("Mora 90+", pct(ult.mora_90), f"▲ {d_m90:+.1f}".replace(".", ",") + f" pp vs. {mes_txt(hace12.fecha_corte)}", CRITICO),
        ("Créditos activos", f"{int(ult.creditos_activos):,}".replace(",", "."), "Consumo · 3 canales", TXT2),
    ]
    for i, t in enumerate(tarjetas):
        tarjeta(fig, 0.05 + i * 0.2275, 0.635, 0.2125, 0.17, *t)

    ax = fig.add_axes([0.075, 0.13, 0.62, 0.43])
    c = c[c.fecha_corte >= "2023-07-01"]
    for canal in ["Digital", "Aliados", "Oficina"]:
        s = c[c.canal == canal]
        ax.plot(s.fecha_corte, s.icv_30, color=COLOR_CANAL[canal], lw=2, solid_capstyle="round",
                zorder=3 if canal == "Aliados" else 2)
        ax.scatter(s.fecha_corte.iloc[-1], s.icv_30.iloc[-1], s=60, color=COLOR_CANAL[canal],
                   edgecolor=SUP, linewidth=2, zorder=4)
        ax.annotate(f"{canal}  {pct(s.icv_30.iloc[-1])}", (s.fecha_corte.iloc[-1], s.icv_30.iloc[-1]),
                    xytext=(10, {"Oficina": 8, "Digital": -8}.get(canal, 0)), textcoords="offset points", va="center", fontsize=11.5, color=TXT1)
    ax.axvline(pd.Timestamp("2024-07-01"), color=EJE, lw=1, zorder=1)
    ax.text(pd.Timestamp("2024-07-10"), 0.115, "Entra nuevo aliado\ncomercial (jul-2024)", fontsize=10.5, color=TXT2, va="top")
    ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: f"{v * 100:.0f} %"))
    ax.set_ylim(0, 0.12)
    ax.xaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: mes_txt(matplotlib.dates.num2date(v))))
    ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonth=[1, 7]))
    ejes_limpios(ax)
    ax.set_title("ICV 30+ por canal (saldo vencido > 30 días / cartera bruta)", loc="left", fontsize=13.5, color=TXT1, pad=12)
    leg = [plt.Line2D([], [], color=COLOR_CANAL[k], lw=2.5, label=k) for k in COLOR_CANAL]
    ax.legend(handles=leg, loc="lower right", frameon=False, ncol=3, fontsize=11.5)

    # Hallazgos
    x0 = 0.785
    fig.text(x0, 0.545, "Hallazgos clave", fontsize=14, weight="semibold")
    puntos = ["El deterioro se concentra\nen el canal Aliados.",
              "Digital y Oficina se\nmantienen estables.",
              "La causa: cambió el perfil\nde los clientes que llegan\npor el nuevo aliado."]
    y = 0.48
    for i, p in enumerate(puntos, 1):
        fig.text(x0, y, f"{i}", fontsize=13, weight="semibold", color=AZUL, va="top")
        fig.text(x0 + 0.022, y, p, fontsize=12, color=TXT2, va="top", linespacing=1.4)
        y -= 0.06 + 0.035 * p.count("\n")
    fig.savefig(IMG / "01_resumen_cartera.png")
    plt.close(fig)


# ---------------------------------------------------------------- 2. Cosechas
def cosechas():
    v = pd.read_csv(RES / "cosechas.csv")
    v = v[v.canal == "Aliados"]
    fig = lienzo("Las cosechas nuevas del canal Aliados se deterioran el doble de rápido",
                 "% de créditos que alguna vez superan 30 días de mora, por trimestre de desembolso (canal Aliados)",
                 "Análisis de cosechas (vintage)")
    ax = fig.add_axes([0.075, 0.13, 0.66, 0.66])
    antes = [q for q in sorted(v.cosecha.unique()) if q < "2024Q3"]
    despues = [q for q in sorted(v.cosecha.unique()) if q >= "2024Q3"]
    for q in antes:
        s = v[(v.cosecha == q) & (v.mes_en_libros <= 18)]
        ax.plot(s.mes_en_libros, s.pct_alguna_vez_30, color=GRIS_SERIE, lw=2, zorder=2)
    for q in despues:
        s = v[(v.cosecha == q) & (v.mes_en_libros <= 18)]
        if s.mes_en_libros.max() < 3:
            continue
        ax.plot(s.mes_en_libros, s.pct_alguna_vez_30, color=NARANJA, lw=2, zorder=3)
        ax.scatter(s.mes_en_libros.iloc[-1], s.pct_alguna_vez_30.iloc[-1], s=56, color=NARANJA,
                   edgecolor=SUP, linewidth=2, zorder=4)
        arriba = q == "2024Q4"
        ax.annotate(q.replace("Q", " T"), (s.mes_en_libros.iloc[-1], s.pct_alguna_vez_30.iloc[-1]),
                    xytext=(0, 12) if arriba else (8, 0), textcoords="offset points", va="center",
                    ha="center" if arriba else "left", fontsize=11, color=TXT2)
    a6 = v[v.cosecha.isin(antes) & (v.mes_en_libros == 6)].pct_alguna_vez_30.mean()
    d6 = v[v.cosecha.isin(despues) & (v.mes_en_libros == 6)].pct_alguna_vez_30.mean()
    ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda x, _: f"{x * 100:.0f} %"))
    ax.set_xlim(1, 19.5)
    ax.set_xticks(range(1, 19, 2) if False else [1, 3, 6, 9, 12, 15, 18])
    ax.set_xlabel("Meses desde el desembolso", fontsize=12, labelpad=8)
    ejes_limpios(ax)
    leg = [plt.Line2D([], [], color=GRIS_SERIE, lw=2.5, label="Cosechas ene-2023 a jun-2024"),
           plt.Line2D([], [], color=NARANJA, lw=2.5, label="Cosechas desde jul-2024 (nuevo aliado)")]
    ax.legend(handles=leg, loc="upper left", frameon=False, fontsize=11.5)

    x0 = 0.78
    tarjeta(fig, x0, 0.6, 0.17, 0.17, "Mora 30+ al mes 6 · antes", pct(a6), "Promedio de 6 cosechas")
    tarjeta(fig, x0, 0.4, 0.17, 0.17, "Mora 30+ al mes 6 · después", pct(d6), f"× {d6 / a6:.1f} veces".replace(".", ","), CRITICO)
    fig.text(x0, 0.33, "Lectura", fontsize=13, weight="semibold")
    fig.text(x0, 0.305, "Cada línea es un trimestre de\ndesembolsos. Las cosechas nuevas\nllegan a la misma mora en menos\nde la mitad del tiempo: el\nproblema está en la originación,\nno en la cobranza.",
             fontsize=11.5, color=TXT2, va="top", linespacing=1.4)
    fig.savefig(IMG / "02_cosechas_vintage.png")
    plt.close(fig)


# ---------------------------------------------------------------- 3. PSI
def psi():
    p = pd.read_csv(RES / "psi.csv")
    nombres = {"score_originacion": "Score de originación", "ingreso_mensual": "Ingreso mensual",
               "edad": "Edad", "monto_desembolsado": "Monto desembolsado", "plazo_meses": "Plazo"}
    orden = ["score_originacion", "ingreso_mensual", "edad", "monto_desembolsado", "plazo_meses"]
    fig = lienzo("El perfil de los clientes de Aliados cambió por completo",
                 "PSI (índice de estabilidad poblacional): población ene-jun 2025 vs. línea base 2023",
                 "Monitoreo de estabilidad (PSI)")
    ax = fig.add_axes([0.2, 0.13, 0.55, 0.66])
    canales = ["Aliados", "Digital", "Oficina"]
    alto, sep = 0.2, 0.04
    for i, var in enumerate(orden):
        for j, canal in enumerate(canales):
            val = p[(p.variable == var) & (p.canal == canal)].psi.iloc[0]
            y = i + (j - 1) * (alto + sep)
            ax.barh(y, val, height=alto, color=COLOR_CANAL[canal], zorder=3)
            ax.text(val + 0.015, y, f"{val:.2f}".replace(".", ","), va="center", fontsize=10.5,
                    color=TXT1 if canal == "Aliados" else MUTED)
    ax.set_yticks(range(len(orden)), [nombres[v] for v in orden], fontsize=12.5, color=TXT1)
    ax.invert_yaxis()
    for umbral in (0.10, 0.25):
        ax.axvline(umbral, color=TXT2, lw=1, zorder=4)
    ax.text(0.10, -0.75, "0,10", ha="center", fontsize=10.5, color=TXT2)
    ax.text(0.25, -0.75, "0,25", ha="center", fontsize=10.5, color=TXT2)
    ax.set_xlim(0, 1.4)
    ax.xaxis.set_major_formatter(mt.FuncFormatter(lambda x, _: f"{x:.1f}".replace(".", ",")))
    ejes_limpios(ax, grid_y=False)
    ax.spines["left"].set_color(EJE)
    leg = [plt.Rectangle((0, 0), 1, 1, color=COLOR_CANAL[c], label=c) for c in canales]
    ax.legend(handles=leg, loc="lower right", frameon=False, fontsize=11.5)

    x0 = 0.79
    fig.text(x0, 0.78, "Cómo leer el PSI", fontsize=13, weight="semibold")
    niveles = [(OK, "✓", "< 0,10", "Población estable"), (ALERTA, "!", "0,10 – 0,25", "Revisar"),
               (CRITICO, "✕", "> 0,25", "Cambio significativo:\nrecalibrar o ajustar política")]
    y = 0.72
    for col, icono, rango, txt in niveles:
        fig.add_artist(plt.Circle((x0 + 0.01, y + 0.005), 0.0105, transform=fig.transFigure, color=col))
        fig.text(x0 + 0.01, y + 0.005, icono, ha="center", va="center", fontsize=10, weight="normal",
                 color="#0b0b0b" if col == ALERTA else "white", fontfamily="Segoe UI Symbol")
        fig.text(x0 + 0.03, y + 0.005, rango, fontsize=12, weight="semibold", va="center")
        fig.text(x0 + 0.03, y - 0.022, txt, fontsize=11, color=TXT2, va="top", linespacing=1.35)
        y -= 0.085 + 0.03 * txt.count("\n")
    fig.text(x0, 0.36, "Resultado", fontsize=13, weight="semibold")
    fig.text(x0, 0.335, "En Aliados, score, ingreso y\nedad superan 0,25: llegan\nclientes más jóvenes, con\nmenor ingreso y menor score.\nDigital y Oficina siguen\nestables.",
             fontsize=11.5, color=TXT2, va="top", linespacing=1.4)
    fig.savefig(IMG / "03_psi_estabilidad.png")
    plt.close(fig)


# ---------------------------------------------------------------- 4. Roll rates
def roll():
    m = pd.read_csv(RES / "roll_rates.csv", index_col=0)
    m.columns = m.columns.astype(int)
    m = m.reindex(columns=range(0, 9), fill_value=0)
    filas = ["Al día", "1-30", "31-60", "61-90", "91-120", "121-150", "151-180"]
    cols = filas + ["Castigo", "Pagado"]
    fig = lienzo("Matriz de rodamiento: de cada 100 créditos en 31-60 días, 64 empeoran",
                 "Probabilidad de pasar de un rango de mora a otro en el mes siguiente (promedio últimos 6 meses)",
                 "Roll rates · Cobranza")
    ax = fig.add_axes([0.13, 0.12, 0.6, 0.62])
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("azul", ["#f4f8fd"] + AZULES)
    ax.imshow(m.values, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.values[i, j]
            if v >= 0.005:
                ax.text(j, i, f"{v * 100:.0f} %", ha="center", va="center", fontsize=11.5,
                        color="white" if v > 0.45 else TXT1, weight="semibold" if j == i + 1 else "normal")
    ax.set_xticks(range(9), cols, fontsize=11.5)
    ax.set_yticks(range(7), filas, fontsize=11.5)
    ax.xaxis.tick_top()
    ax.set_xticks(np.arange(-0.5, 9), minor=True)
    ax.set_yticks(np.arange(-0.5, 7), minor=True)
    ax.grid(which="minor", color=SUP, lw=3)
    ax.tick_params(length=0, which="both", colors=TXT1)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.text(0.13, 0.8, "Mes siguiente →", fontsize=11, color=MUTED)
    fig.text(0.06, 0.43, "Mes actual ↓", fontsize=11, color=MUTED, rotation=90, va="center")

    x0 = 0.77
    fig.text(x0, 0.74, "Lectura", fontsize=13, weight="semibold")
    texto = ("La diagonal en negrita muestra el\nrodamiento a un peor rango.\n\n"
             f"• 1-30 días: {m.loc[1, 0] * 100:.0f} % se cura.\n"
             f"• 31-60 días: solo {m.loc[2, 0] * 100:.0f} % se cura.\n"
             f"• Desde 61 días, más del {min(m.loc[3, 4], m.loc[4, 5], m.loc[5, 6]) * 100:.0f} %\n   sigue rodando.\n\n"
             "Recomendación: concentrar la\ngestión de cobranza en el rango\n1-30, antes de que el crédito\nllegue a 31-60.")
    fig.text(x0, 0.71, texto, fontsize=11.5, color=TXT2, va="top", linespacing=1.4)
    fig.savefig(IMG / "04_roll_rates.png")
    plt.close(fig)


# ---------------------------------------------------------------- 5. Simulación
def simulacion():
    s = pd.read_csv(RES / "simulacion_corte_score.csv")
    ref = s.referencia_otros_canales.iloc[0]
    etiquetas = ["Sin corte" if str(x) == "Sin corte" else f"≥ {x}" for x in s.score_minimo]
    rec = etiquetas.index("≥ 600")
    fig = lienzo("Propuesta: score mínimo de 600 en el canal Aliados",
                 "Simulación sobre los créditos de Aliados desembolsados entre jul-2024 y jun-2025",
                 "Simulación de política de crédito")
    x = np.arange(len(etiquetas))
    ax1 = fig.add_axes([0.075, 0.15, 0.4, 0.53])
    ax2 = fig.add_axes([0.545, 0.15, 0.4, 0.53])
    for ax, col, titulo, fmt in [(ax1, "mora_30_6m", "Mora 30+ en los primeros 6 meses", 1),
                                 (ax2, "pct_volumen_aprobado", "Volumen de créditos que se aprueba", 0)]:
        colores = [AZUL if i == rec else "#9ec5f4" for i in range(len(x))]
        ax.bar(x, s[col], width=0.5, color=colores, zorder=3)
        for i, v in enumerate(s[col]):
            ax.text(i, v + (0.004 if fmt else 0.02), pct(v, fmt), ha="center", fontsize=11.5,
                    color=TXT1, weight="semibold" if i == rec else "normal", zorder=5,
                    bbox=dict(fc=SUP, ec="none", pad=1.5))
        ax.set_xticks(x, etiquetas, fontsize=11.5)
        ax.set_title(titulo, loc="left", fontsize=13.5, pad=14)
        ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: f"{v * 100:.0f} %"))
        ejes_limpios(ax)
        ax.set_xlabel("Score mínimo exigido", fontsize=11.5, labelpad=8)
    ax1.hlines(ref, -0.5, len(x) - 0.55, color=TXT2, lw=1, zorder=4)
    ax1.set_xlim(-0.5, len(x) + 0.3)
    ax1.text(len(x) - 0.45, ref, f"Digital +\nOficina\n{pct(ref)}", ha="left", va="center", fontsize=10.5, color=TXT2, linespacing=1.3)
    ax1.set_ylim(0, 0.16)
    ax2.set_ylim(0, 1.15)
    r = s.iloc[rec]
    fig.text(0.05, 0.79, f"Con score ≥ 600 la mora temprana baja de {pct(s.mora_30_6m.iloc[0])} a {pct(r.mora_30_6m)}, "
                         f"cerca de los otros canales, aprobando el {pct(r.pct_volumen_aprobado, 0)} del volumen.",
             fontsize=12.5, color=TXT1)
    fig.savefig(IMG / "05_simulacion_politica.png")
    plt.close(fig)


# ---------------------------------------------------------------- 0. Portada
def portada():
    k = pd.read_csv(RES / "kpis_mensuales.csv", parse_dates=["fecha_corte"])
    s = pd.read_csv(RES / "simulacion_corte_score.csv")
    fig = plt.figure(figsize=(12, 7.5), dpi=160)
    fig.patch.set_facecolor(SUP)
    fig.add_artist(plt.Rectangle((0, 0), 0.012, 1, transform=fig.transFigure, color=AZUL))
    fig.text(0.07, 0.86, "CASO DE ESTUDIO · RIESGO DE CRÉDITO", fontsize=12, color=MUTED, weight="semibold")
    fig.text(0.07, 0.72, "¿Por qué sube la mora\nsi la cartera está creciendo?", fontsize=40, weight="semibold",
             va="center", linespacing=1.15)
    fig.text(0.07, 0.565, "Diagnóstico de una cartera de consumo de una fintech: KPIs, cosechas,\n"
                          "roll rates, estabilidad poblacional (PSI) y simulación de política de crédito.",
             fontsize=15, color=TXT2, va="center", linespacing=1.5)
    r = s[s.score_minimo.astype(str) == "600"].iloc[0]
    datos = [(f"$ {k.cartera_bruta.iloc[-1] / 1e9:,.1f} mil M".replace(".", ","), "de cartera analizada"),
             (f"{len(pd.read_csv(RAIZ / 'datos' / 'creditos.csv')):,}".replace(",", "."), "créditos · 36 meses"),
             (f"{pct(s.mora_30_6m.iloc[0])} → {pct(r.mora_30_6m)}", "mora temprana con la\npolítica propuesta")]
    for i, (v, t) in enumerate(datos):
        x = 0.07 + i * 0.29
        fig.text(x, 0.40, v, fontsize=30, weight="semibold", color=TXT1)
        fig.text(x, 0.355, t, fontsize=13, color=TXT2, va="top", linespacing=1.35)
    x = 0.07
    for h in ["Python", "SQL Server", "Power BI · DAX", "Análisis de riesgo"]:
        w = 0.012 * len(h) * 0.72 + 0.03
        fig.add_artist(FancyBboxPatch((x, 0.15), w, 0.055, boxstyle="round,pad=0,rounding_size=0.02",
                                      transform=fig.transFigure, fc=PLANO, ec=GRID, lw=1))
        fig.text(x + w / 2, 0.1775, h, fontsize=12.5, ha="center", va="center", color=TXT1)
        x += w + 0.015
    fig.text(0.07, 0.07, AUTOR, fontsize=12, color=TXT1, weight="semibold")
    fig.text(0.95, 0.07, "Datos sintéticos · empresa ficticia", fontsize=10.5, color=MUTED, ha="right")
    fig.savefig(IMG / "00_portada.png")
    plt.close(fig)


if __name__ == "__main__":
    for f in (portada, resumen, cosechas, psi, roll, simulacion):
        f()
        print("ok", f.__name__)
