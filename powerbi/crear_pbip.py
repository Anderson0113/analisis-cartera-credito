"""
Genera el proyecto de Power BI (PBIP) del caso de cartera.
Uso: python crear_pbip.py   ->  powerbi/CarteraCrediAndes/CarteraCrediAndes.pbip
AVISO: regenera el proyecto desde cero y reemplaza la versión guardada por Power BI (incluida la caché de datos).
"""
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI / "herramientas"))
from pbip_builder import (SIN_TOTALES_MATRIZ, SIN_TOTALES_TABLA, color_unico, colores_serie, escala_fondo,  # noqa: E402
                          escribir_pbip, modelo, relacion, reporte,
                          tabla_calendario, tabla_csv, tabla_m, tabla_medidas, texto, visual)

CANALES = {"Digital": "#2a78d6", "Aliados": "#eb6834", "Oficina": "#1baf7a"}
COLOR_COSECHA = {f"{a} T{t}": ("#eb6834" if (a, t) >= (2024, 3) else "#c3c2b7") for a in (2023, 2024, 2025) for t in (1, 2, 3, 4)}

DATOS = str(AQUI.parent / "datos")
PCT, ENT, COP = "0.0 %;-0.0 %;0.0 %", "#,0", "\\$ #,0"
TXT1, TXT2 = "#0b0b0b", "#52514e"

# ------------------------------------------------------------------ tablas
creditos = tabla_csv("creditos", "creditos.csv", [
    ("id_credito", "string"), ("fecha_desembolso", "dateTime", {"formatString": "dd/mm/yyyy"}),
    ("canal", "string"), ("producto", "string"), ("ciudad", "string", {"dataCategory": "City"}),
    ("score_originacion", "int64"), ("ingreso_mensual", "int64", {"formatString": COP}),
    ("edad", "int64"), ("monto_desembolsado", "int64", {"formatString": COP, "summarizeBy": "sum"}),
    ("plazo_meses", "int64"), ("tasa_ea", "double", {"formatString": PCT}), ("banda_score", "string"),
])

desempeno = tabla_csv("desempeno_mensual", "desempeno_mensual.csv", [
    ("id_credito", "string"), ("fecha_corte", "dateTime", {"formatString": "dd/mm/yyyy"}),
    ("meses_en_libros", "int64"), ("estado_mora", "int64", {"isHidden": True}),
    ("saldo_capital", "int64", {"formatString": COP, "summarizeBy": "sum"}),
    ("rango_mora", "string", {"sortByColumn": "estado_mora"}),
])

cosechas = tabla_csv("cosechas", "resultados\\cosechas.csv", [
    ("canal", "string"), ("cosecha", "string", {"como": "Cosecha"}), ("mes_en_libros", "int64", {"como": "Meses desde el desembolso"}),
    ("creditos", "int64"), ("pct_alguna_vez_30", "double", {"formatString": PCT}),
], pasos_extra=['Table.ReplaceValue(#PREV, "Q", " T", Replacer.ReplaceText, {"cosecha"})'])

psi = tabla_csv("psi", "resultados\\psi.csv", [
    ("canal", "string", {"como": "Canal"}), ("variable", "string", {"como": "Variable"}), ("psi", "double", {"formatString": "0.00"}),
], pasos_extra=[
    'Table.TransformColumns(#PREV, {{"variable", each Record.FieldOrDefault([score_originacion = "Score de originación", '
    'ingreso_mensual = "Ingreso mensual", edad = "Edad", monto_desembolsado = "Monto desembolsado", plazo_meses = "Plazo"], _, _), type text}})',
    'Table.AddColumn(#PREV, "Diagnóstico", each if [psi] < 0.1 then "Estable" else if [psi] < 0.25 then "Revisar" else "Cambio significativo", type text)',
])
psi["columns"].append({"name": "Diagnóstico", "dataType": "string", "sourceColumn": "Diagnóstico", "summarizeBy": "none",
                       "lineageTag": "psi-diagnostico"})

simulacion = tabla_csv("simulacion", "resultados\\simulacion_corte_score.csv", [
    ("score_minimo", "string", {"sortByColumn": "orden", "como": "Score mínimo"}), ("pct_volumen_aprobado", "double", {"formatString": PCT}),
    ("mora_30_6m", "double", {"formatString": PCT}), ("creditos_aprobados", "int64"),
    ("referencia_otros_canales", "double", {"formatString": PCT}),
], pasos_extra=[
    'Table.AddColumn(#PREV, "orden", each if [score_minimo] = "Sin corte" then 0 else Number.From([score_minimo]), Int64.Type)',
    'Table.TransformColumns(#PREV, {{"score_minimo", each if _ = "Sin corte" then _ else "≥ " & _, type text}})',
])
simulacion["columns"].append({"name": "orden", "dataType": "int64", "sourceColumn": "orden", "summarizeBy": "none",
                              "isHidden": True, "lineageTag": "sim-orden"})

ETIQ = '{"Al día", "1-30", "31-60", "61-90", "91-120", "121-150", "151-180", "Castigo", "Pagado"}'
roll = tabla_m("roll_rates", [
    ("estado_desde", "int64", {"isHidden": True}), ("estado_hasta", "int64", {"isHidden": True}),
    ("probabilidad", "double", {"formatString": "0 %"}),
    ("Mes actual", "string", {"sortByColumn": "estado_desde"}), ("Mes siguiente", "string", {"sortByColumn": "estado_hasta"}),
], [
    "let",
    '    Origen = Csv.Document(File.Contents(RutaDatos & "\\resultados\\roll_rates.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
    "    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),",
    '    Despivote = Table.UnpivotOtherColumns(Encabezados, {"estado_mora"}, "estado_hasta", "probabilidad"),',
    '    Renombre = Table.RenameColumns(Despivote, {{"estado_mora", "estado_desde"}}),',
    '    Tipos = Table.TransformColumnTypes(Renombre, {{"estado_desde", Int64.Type}, {"estado_hasta", Int64.Type}, {"probabilidad", type number}}, "en-US"),',
    f"    Etiquetas = {ETIQ},",
    '    Desde = Table.AddColumn(Tipos, "Mes actual", each Etiquetas{[estado_desde]}, type text),',
    '    Hasta = Table.AddColumn(Desde, "Mes siguiente", each Etiquetas{[estado_hasta]}, type text)',
    "in",
    "    Hasta",
])

medidas = tabla_medidas("Medidas", [
    ("Cartera Bruta", "CALCULATE ( SUM ( desempeno_mensual[saldo_capital] ), desempeno_mensual[estado_mora] <= 6 )", COP, "Cartera"),
    ("Cartera Vencida 30+", "CALCULATE ( SUM ( desempeno_mensual[saldo_capital] ), desempeno_mensual[estado_mora] >= 2, desempeno_mensual[estado_mora] <= 6 )", COP, "Cartera"),
    ("Cartera Mora 90+", "CALCULATE ( SUM ( desempeno_mensual[saldo_capital] ), desempeno_mensual[estado_mora] >= 4, desempeno_mensual[estado_mora] <= 6 )", COP, "Cartera"),
    ("ICV 30+", "DIVIDE ( [Cartera Vencida 30+], [Cartera Bruta] )", PCT, "Indicadores"),
    ("Mora 90+", "DIVIDE ( [Cartera Mora 90+], [Cartera Bruta] )", PCT, "Indicadores"),
    ("Créditos Activos", "CALCULATE ( DISTINCTCOUNT ( desempeno_mensual[id_credito] ), desempeno_mensual[estado_mora] <= 6 )", ENT, "Cartera"),
    ("Castigos", "CALCULATE ( SUM ( desempeno_mensual[saldo_capital] ), desempeno_mensual[estado_mora] = 7 )", COP, "Cartera"),
    ("Desembolsos", "CALCULATE ( SUM ( creditos[monto_desembolsado] ), USERELATIONSHIP ( creditos[fecha_desembolso], Calendario[Fecha] ) )", COP, "Cartera"),
    ("Último Corte", "CALCULATE ( MAX ( desempeno_mensual[fecha_corte] ), ALL ( Calendario ) )", "mmm yyyy", "Indicadores"),
    ("Cartera Bruta (último corte)", "VAR u = [Último Corte] RETURN CALCULATE ( [Cartera Bruta], Calendario[Fecha] = u )", COP, "Último corte"),
    ("ICV 30+ (último corte)", "VAR u = [Último Corte] RETURN CALCULATE ( [ICV 30+], Calendario[Fecha] = u )", PCT, "Último corte"),
    ("Mora 90+ (último corte)", "VAR u = [Último Corte] RETURN CALCULATE ( [Mora 90+], Calendario[Fecha] = u )", PCT, "Último corte"),
    ("Créditos Activos (último corte)", "VAR u = [Último Corte] RETURN CALCULATE ( [Créditos Activos], Calendario[Fecha] = u )", ENT, "Último corte"),
    ("ICV 30+ hace 12 meses", "VAR u = EDATE ( [Último Corte], -12 ) RETURN CALCULATE ( [ICV 30+], Calendario[Fecha] = u )", PCT, "Último corte"),
    ("Var ICV 30+ 12M (pp)", "( [ICV 30+ (último corte)] - [ICV 30+ hace 12 meses] ) * 100", "+0.0 \"pp\";-0.0 \"pp\"", "Último corte"),
    ("Mora 30+ cosecha", "AVERAGE ( cosechas[pct_alguna_vez_30] )", PCT, "Análisis"),
    ("PSI", "SUM ( psi[psi] )", "0.00", "Análisis"),
    ("Probabilidad de rodamiento", "SUM ( roll_rates[probabilidad] )", "0 %", "Análisis"),
    ("Mora 30+ 6 meses (simulada)", "SUM ( simulacion[mora_30_6m] )", PCT, "Análisis"),
    ("Volumen aprobado (simulado)", "SUM ( simulacion[pct_volumen_aprobado] )", "0 %", "Análisis"),
])

tablas = [creditos, desempeno, tabla_calendario("2023-01-01", "2025-12-31"), cosechas, psi, simulacion, roll, medidas]
relaciones = [
    relacion("desempeno_mensual.id_credito", "creditos.id_credito"),
    relacion("desempeno_mensual.fecha_corte", "Calendario.Fecha"),
    relacion("creditos.fecha_desembolso", "Calendario.Fecha", activa=False),
]


# ------------------------------------------------------------------ páginas
def encabezado(titulo, sub):
    return texto(20, 8, 1240, 64, [(titulo, 20, True, TXT1), (sub, 11, False, TXT2)])


M = "Medidas"
p1 = [
    encabezado("Cartera de consumo · Resumen", "CrediAndes (empresa ficticia, datos sintéticos) · cifras al último corte"),
    visual("card", 20, 80, 300, 110, {"Values": [(M, "Cartera Bruta (último corte)", True)]}, "Cartera bruta"),
    visual("card", 335, 80, 300, 110, {"Values": [(M, "ICV 30+ (último corte)", True)]}, "ICV 30+"),
    visual("card", 650, 80, 300, 110, {"Values": [(M, "Mora 90+ (último corte)", True)]}, "Mora 90+"),
    visual("card", 965, 80, 295, 110, {"Values": [(M, "Var ICV 30+ 12M (pp)", True)]}, "Variación ICV 30+ en 12 meses"),
    visual("lineChart", 20, 205, 900, 495, {"Category": [("Calendario", "Inicio de mes", False)],
                                            "Y": [(M, "ICV 30+", True)], "Series": [("creditos", "canal", False)]},
           "ICV 30+ por canal", colores_serie("creditos", "canal", CANALES)),
    visual("slicer", 940, 205, 320, 150, {"Values": [("creditos", "canal", False)]}, "Canal"),
    visual("slicer", 940, 370, 320, 150, {"Values": [("creditos", "producto", False)]}, "Producto"),
    visual("slicer", 940, 535, 320, 165, {"Values": [("creditos", "ciudad", False)]}, "Ciudad"),
]
p2 = [
    encabezado("Cosechas (vintage)", "% de créditos que alguna vez superan 30 días de mora, por trimestre de desembolso"),
    visual("slicer", 20, 80, 300, 150, {"Values": [("cosechas", "canal", False)]}, "Canal"),
    visual("lineChart", 340, 80, 920, 620, {"Category": [("cosechas", "Meses desde el desembolso", False)],
                                            "Y": [(M, "Mora 30+ cosecha", True)], "Series": [("cosechas", "Cosecha", False)]},
           "Mora 30+ acumulada · gris: antes de jul-2024 · naranja: desde jul-2024",
           colores_serie("cosechas", "Cosecha", COLOR_COSECHA)),
    texto(20, 250, 300, 300, [("Cómo leer", 12, True, TXT1),
                              ("Cada línea es un trimestre de desembolsos. Si las cosechas nuevas suben más rápido, "
                               "el problema está en la originación, no en la cobranza.", 11, False, TXT2),
                              ("Selecciona Aliados en el filtro de canal para ver el cambio.", 11, True, TXT1)]),
]
p3 = [
    encabezado("Matriz de rodamiento (roll rates)", "Probabilidad de pasar de un rango de mora a otro en el mes siguiente · últimos 6 meses"),
    visual("pivotTable", 20, 80, 1240, 620, {"Rows": [("roll_rates", "Mes actual", False)],
                                             "Columns": [("roll_rates", "Mes siguiente", False)],
                                             "Values": [(M, "Probabilidad de rodamiento", True)]}, "Mes actual → mes siguiente",
           SIN_TOTALES_MATRIZ | escala_fondo(M, "Probabilidad de rodamiento", "#f4f8fd", "#3987e5")),
]
p4 = [
    encabezado("Estabilidad poblacional (PSI)", "Población ene-jun 2025 frente a la línea base 2023 · < 0,10 estable · 0,10-0,25 revisar · > 0,25 cambio significativo"),
    visual("clusteredBarChart", 20, 80, 860, 620, {"Category": [("psi", "Variable", False)], "Y": [(M, "PSI", True)],
                                                   "Series": [("psi", "Canal", False)]}, "PSI por variable y canal",
           colores_serie("psi", "Canal", CANALES) | {"labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]}),
    visual("tableEx", 900, 80, 360, 620, {"Values": [("psi", "Canal", False), ("psi", "Variable", False),
                                                     (M, "PSI", True), ("psi", "Diagnóstico", False)]}, "Detalle",
           SIN_TOTALES_TABLA),
]
p5 = [
    encabezado("Simulación de política: score mínimo en Aliados", "Créditos de Aliados desembolsados entre jul-2024 y jun-2025"),
    visual("clusteredColumnChart", 20, 80, 615, 620, {"Category": [("simulacion", "Score mínimo", False)],
                                                      "Y": [(M, "Mora 30+ 6 meses (simulada)", True)]}, "Mora 30+ en los primeros 6 meses",
           color_unico("#2a78d6")),
    visual("clusteredColumnChart", 645, 80, 615, 620, {"Category": [("simulacion", "Score mínimo", False)],
                                                       "Y": [(M, "Volumen aprobado (simulado)", True)]}, "Volumen de créditos que se aprueba",
           color_unico("#2a78d6")),
]

if __name__ == "__main__":
    salida = AQUI / "CarteraCrediAndes"
    salida.mkdir(exist_ok=True)
    ruta = escribir_pbip(salida, "CarteraCrediAndes", modelo(tablas, relaciones, DATOS),
                         reporte([("Resumen", p1), ("Cosechas", p2), ("Roll rates", p3), ("PSI", p4), ("Simulación", p5)]))
    print(ruta)
