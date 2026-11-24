# Modelo y medidas DAX para el tablero de Power BI

## Modelo (esquema estrella)

| Tabla | Tipo | Origen | Relación |
|---|---|---|---|
| `desempeno_mensual` | Hechos | `datos/desempeno_mensual.csv` | `id_credito` → `creditos`; `fecha_corte` → `Calendario[Fecha]` |
| `creditos` | Dimensión | `datos/creditos.csv` | 1 a muchos con `desempeno_mensual` |
| `Calendario` | Dimensión | Tabla DAX (abajo) | 1 a muchos con `fecha_corte` |
| `cosechas`, `roll_rates`, `psi`, `simulacion_corte_score` | Tablas de apoyo | `datos/resultados/*.csv` | Sin relación (visuales propios) |

```DAX
Calendario =
ADDCOLUMNS (
    CALENDAR ( DATE ( 2023, 1, 1 ), DATE ( 2025, 12, 31 ) ),
    "Año", YEAR ( [Date] ),
    "Mes", FORMAT ( [Date], "mmm-yyyy" ),
    "MesNum", YEAR ( [Date] ) * 100 + MONTH ( [Date] ),
    "Trimestre", YEAR ( [Date] ) & " T" & QUARTER ( [Date] )
)
```

## Medidas

```DAX
Cartera Bruta =
CALCULATE (
    SUM ( desempeno_mensual[saldo_capital] ),
    desempeno_mensual[estado_mora] <= 6
)

Cartera Vencida 30+ =
CALCULATE (
    SUM ( desempeno_mensual[saldo_capital] ),
    desempeno_mensual[estado_mora] >= 2,
    desempeno_mensual[estado_mora] <= 6
)

ICV 30+ = DIVIDE ( [Cartera Vencida 30+], [Cartera Bruta] )

Cartera Mora 90+ =
CALCULATE (
    SUM ( desempeno_mensual[saldo_capital] ),
    desempeno_mensual[estado_mora] >= 4,
    desempeno_mensual[estado_mora] <= 6
)

Mora 90+ = DIVIDE ( [Cartera Mora 90+], [Cartera Bruta] )

Créditos Activos =
CALCULATE (
    DISTINCTCOUNT ( desempeno_mensual[id_credito] ),
    desempeno_mensual[estado_mora] <= 6
)

Castigos =
CALCULATE (
    SUM ( desempeno_mensual[saldo_capital] ),
    desempeno_mensual[estado_mora] = 7
)

Desembolsos =
CALCULATE (
    SUM ( creditos[monto_desembolsado] ),
    USERELATIONSHIP ( creditos[fecha_desembolso], Calendario[Date] )
)
-- Requiere una relación inactiva creditos[fecha_desembolso] → Calendario[Date]

ICV 30+ Hace 12 Meses =
CALCULATE ( [ICV 30+], DATEADD ( Calendario[Date], -12, MONTH ) )

Var ICV 30+ (pp) = ( [ICV 30+] - [ICV 30+ Hace 12 Meses] ) * 100

Crecimiento Cartera 12M =
DIVIDE (
    [Cartera Bruta],
    CALCULATE ( [Cartera Bruta], DATEADD ( Calendario[Date], -12, MONTH ) )
) - 1

-- Último corte disponible, útil para tarjetas que deben ignorar el filtro de fecha
ICV 30+ Último Corte =
VAR UltimoCorte = MAX ( desempeno_mensual[fecha_corte] )
RETURN
    CALCULATE ( [ICV 30+], desempeno_mensual[fecha_corte] = UltimoCorte )

-- Color condicional para tarjetas y semáforos
Color ICV =
SWITCH (
    TRUE (),
    [ICV 30+] < 0.05, "#0ca30c",
    [ICV 30+] < 0.07, "#fab219",
    "#d03b3b"
)

-- Semáforo de PSI (tabla psi)
Estado PSI =
VAR v = MAX ( psi[psi] )
RETURN
    SWITCH ( TRUE (), v < 0.10, "Estable", v < 0.25, "Revisar", "Cambio significativo" )
```

## Páginas sugeridas del tablero

1. **Resumen ejecutivo:** tarjetas (cartera, ICV 30+, mora 90+, créditos activos), línea de ICV 30+ por canal y segmentadores de canal, producto y ciudad.
2. **Cosechas:** gráfico de líneas (`cosechas`) con eje X = mes en libros, leyenda = cosecha, filtro de canal.
3. **Roll rates:** matriz con formato condicional de escala azul.
4. **Estabilidad (PSI):** barras por variable y canal, con líneas de referencia en 0,10 y 0,25.
5. **Simulación de política:** barras de mora y volumen por punto de corte, con un parámetro *What-if* para el score mínimo.
