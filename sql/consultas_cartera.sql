/* =====================================================================
   Caso de portafolio: Análisis de cartera de consumo (CrediAndes, ficticia)
   Motor: SQL Server (T-SQL)
   Tablas: dbo.creditos, dbo.desempeno_mensual  (cargadas desde los CSV de /datos)
   Autor: Anderson Barrero
   ===================================================================== */

/* ---------------------------------------------------------------------
   0. Estructura de tablas
   --------------------------------------------------------------------- */
CREATE TABLE dbo.creditos (
    id_credito          VARCHAR(10)   NOT NULL PRIMARY KEY,
    fecha_desembolso    DATE          NOT NULL,
    canal               VARCHAR(20)   NOT NULL,
    producto            VARCHAR(30)   NOT NULL,
    ciudad              VARCHAR(30)   NOT NULL,
    score_originacion   INT           NOT NULL,
    ingreso_mensual     BIGINT        NOT NULL,
    edad                INT           NOT NULL,
    monto_desembolsado  BIGINT        NOT NULL,
    plazo_meses         INT           NOT NULL,
    tasa_ea             DECIMAL(6,4)  NOT NULL,
    banda_score         VARCHAR(10)   NOT NULL
);

CREATE TABLE dbo.desempeno_mensual (
    id_credito       VARCHAR(10)  NOT NULL REFERENCES dbo.creditos(id_credito),
    fecha_corte      DATE         NOT NULL,
    meses_en_libros  INT          NOT NULL,
    estado_mora      TINYINT      NOT NULL,  -- 0 al día, 1 = 1-30 ... 6 = 151-180, 7 castigado, 8 pagado
    saldo_capital    BIGINT       NOT NULL,
    rango_mora       VARCHAR(12)  NOT NULL,
    CONSTRAINT PK_desempeno PRIMARY KEY (id_credito, fecha_corte)
);
CREATE INDEX IX_desempeno_corte ON dbo.desempeno_mensual (fecha_corte, estado_mora) INCLUDE (saldo_capital);


/* ---------------------------------------------------------------------
   1. KPIs mensuales: cartera bruta, ICV 30+ y mora 90+
   --------------------------------------------------------------------- */
SELECT
    d.fecha_corte,
    SUM(d.saldo_capital)                                                    AS cartera_bruta,
    SUM(CASE WHEN d.estado_mora >= 2 THEN d.saldo_capital ELSE 0 END)        AS cartera_vencida_30,
    CAST(SUM(CASE WHEN d.estado_mora >= 2 THEN d.saldo_capital ELSE 0 END) AS FLOAT)
        / NULLIF(SUM(d.saldo_capital), 0)                                   AS icv_30,
    CAST(SUM(CASE WHEN d.estado_mora >= 4 THEN d.saldo_capital ELSE 0 END) AS FLOAT)
        / NULLIF(SUM(d.saldo_capital), 0)                                   AS mora_90,
    COUNT(*)                                                                AS creditos_activos
FROM dbo.desempeno_mensual AS d
WHERE d.estado_mora BETWEEN 0 AND 6          -- solo cartera viva
GROUP BY d.fecha_corte
ORDER BY d.fecha_corte;


/* ---------------------------------------------------------------------
   2. ICV 30+ por canal y variación frente a 12 meses atrás
   --------------------------------------------------------------------- */
WITH icv AS (
    SELECT
        d.fecha_corte,
        c.canal,
        CAST(SUM(CASE WHEN d.estado_mora >= 2 THEN d.saldo_capital ELSE 0 END) AS FLOAT)
            / NULLIF(SUM(d.saldo_capital), 0) AS icv_30
    FROM dbo.desempeno_mensual AS d
    JOIN dbo.creditos AS c ON c.id_credito = d.id_credito
    WHERE d.estado_mora BETWEEN 0 AND 6
    GROUP BY d.fecha_corte, c.canal
)
SELECT
    fecha_corte,
    canal,
    icv_30,
    icv_30 - LAG(icv_30, 12) OVER (PARTITION BY canal ORDER BY fecha_corte) AS variacion_12m_pp
FROM icv
ORDER BY canal, fecha_corte;


/* ---------------------------------------------------------------------
   3. Cosechas (vintage): % de créditos que alguna vez llegan a 30+ días,
      por trimestre de desembolso y mes en libros
   --------------------------------------------------------------------- */
WITH base AS (
    SELECT
        c.canal,
        CONCAT(YEAR(c.fecha_desembolso), 'T', DATEPART(QUARTER, c.fecha_desembolso)) AS cosecha,
        d.id_credito,
        d.meses_en_libros,
        MAX(CASE WHEN d.estado_mora BETWEEN 2 AND 7 THEN 1 ELSE 0 END)
            OVER (PARTITION BY d.id_credito ORDER BY d.meses_en_libros
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS alguna_vez_30
    FROM dbo.desempeno_mensual AS d
    JOIN dbo.creditos AS c ON c.id_credito = d.id_credito
    WHERE d.meses_en_libros BETWEEN 1 AND 24
),
tamano AS (
    SELECT canal,
           CONCAT(YEAR(fecha_desembolso), 'T', DATEPART(QUARTER, fecha_desembolso)) AS cosecha,
           COUNT(*) AS creditos
    FROM dbo.creditos
    GROUP BY canal, CONCAT(YEAR(fecha_desembolso), 'T', DATEPART(QUARTER, fecha_desembolso))
)
SELECT
    b.canal,
    b.cosecha,
    b.meses_en_libros,
    t.creditos,
    CAST(SUM(b.alguna_vez_30) AS FLOAT) / t.creditos AS pct_alguna_vez_30
    -- Nota: los créditos que ya se pagaron dejan de aparecer; en Python se arrastra su último estado.
FROM base AS b
JOIN tamano AS t ON t.canal = b.canal AND t.cosecha = b.cosecha
GROUP BY b.canal, b.cosecha, b.meses_en_libros, t.creditos
ORDER BY b.canal, b.cosecha, b.meses_en_libros;


/* ---------------------------------------------------------------------
   4. Matriz de rodamiento (roll rates), últimos 6 meses
   --------------------------------------------------------------------- */
DECLARE @ultimo_corte DATE = (SELECT MAX(fecha_corte) FROM dbo.desempeno_mensual);

WITH transiciones AS (
    SELECT
        d.estado_mora AS estado_actual,
        LEAD(d.estado_mora) OVER (PARTITION BY d.id_credito ORDER BY d.fecha_corte) AS estado_siguiente,
        d.fecha_corte
    FROM dbo.desempeno_mensual AS d
)
SELECT
    estado_actual,
    estado_siguiente,
    COUNT(*) AS creditos,
    CAST(COUNT(*) AS FLOAT) / SUM(COUNT(*)) OVER (PARTITION BY estado_actual) AS probabilidad
FROM transiciones
WHERE estado_siguiente IS NOT NULL
  AND estado_actual BETWEEN 0 AND 6
  AND fecha_corte >= DATEADD(MONTH, -6, @ultimo_corte)
  AND fecha_corte <  @ultimo_corte
GROUP BY estado_actual, estado_siguiente
ORDER BY estado_actual, estado_siguiente;


/* ---------------------------------------------------------------------
   5. PSI del score de originación por canal
      Línea base: desembolsos 2023 (deciles). Población actual: ene-jun 2025.
   --------------------------------------------------------------------- */
WITH base AS (
    SELECT canal, score_originacion,
           NTILE(10) OVER (PARTITION BY canal ORDER BY score_originacion) AS decil
    FROM dbo.creditos
    WHERE YEAR(fecha_desembolso) = 2023
),
cortes AS (   -- límite superior de cada decil en la línea base
    SELECT canal, decil, MAX(score_originacion) AS limite
    FROM base GROUP BY canal, decil
),
dist_base AS (
    SELECT canal, decil, CAST(COUNT(*) AS FLOAT) / SUM(COUNT(*)) OVER (PARTITION BY canal) AS pct_base
    FROM base GROUP BY canal, decil
),
actual AS (
    SELECT c.canal,
           COALESCE((SELECT MIN(k.decil) FROM cortes AS k
                     WHERE k.canal = c.canal AND c.score_originacion <= k.limite), 10) AS decil
    FROM dbo.creditos AS c
    WHERE c.fecha_desembolso BETWEEN '2025-01-01' AND '2025-06-30'
),
dist_actual AS (
    SELECT canal, decil, CAST(COUNT(*) AS FLOAT) / SUM(COUNT(*)) OVER (PARTITION BY canal) AS pct_actual
    FROM actual GROUP BY canal, decil
)
SELECT
    b.canal,
    SUM((COALESCE(a.pct_actual, 0.0001) - b.pct_base)
        * LOG(COALESCE(a.pct_actual, 0.0001) / b.pct_base)) AS psi_score,
    CASE
        WHEN SUM((COALESCE(a.pct_actual, 0.0001) - b.pct_base) * LOG(COALESCE(a.pct_actual, 0.0001) / b.pct_base)) < 0.10 THEN 'Estable'
        WHEN SUM((COALESCE(a.pct_actual, 0.0001) - b.pct_base) * LOG(COALESCE(a.pct_actual, 0.0001) / b.pct_base)) < 0.25 THEN 'Revisar'
        ELSE 'Cambio significativo'
    END AS diagnostico
FROM dist_base AS b
LEFT JOIN dist_actual AS a ON a.canal = b.canal AND a.decil = b.decil
GROUP BY b.canal;


/* ---------------------------------------------------------------------
   6. Simulación de punto de corte: mora 30+ en los primeros 6 meses
      para Aliados (desembolsos jul-2024 a jun-2025)
   --------------------------------------------------------------------- */
WITH marca AS (
    SELECT c.id_credito, c.score_originacion,
           MAX(CASE WHEN d.estado_mora BETWEEN 2 AND 7 THEN 1 ELSE 0 END) AS mora_30_6m
    FROM dbo.creditos AS c
    JOIN dbo.desempeno_mensual AS d
      ON d.id_credito = c.id_credito AND d.meses_en_libros BETWEEN 1 AND 6
    WHERE c.canal = 'Aliados'
      AND c.fecha_desembolso BETWEEN '2024-07-01' AND '2025-06-30'
    GROUP BY c.id_credito, c.score_originacion
),
escenarios AS (
    SELECT corte FROM (VALUES (0), (550), (575), (600), (625), (650)) AS v(corte)
)
SELECT
    e.corte                                                       AS score_minimo,
    CAST(COUNT(m.id_credito) AS FLOAT) / (SELECT COUNT(*) FROM marca) AS pct_volumen_aprobado,
    AVG(CAST(m.mora_30_6m AS FLOAT))                              AS mora_30_6m
FROM escenarios AS e
JOIN marca AS m ON m.score_originacion >= e.corte
GROUP BY e.corte
ORDER BY e.corte;
