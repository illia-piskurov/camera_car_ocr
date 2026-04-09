import sqlite3

DB = "backend/data/app.db"
TARGETS = ("BM8718EB", "F9099CY")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=== Target plate events ===")
rows = cur.execute(
    """
    SELECT
      id,
      occurred_at,
      frame_id,
      plate,
      zone_name,
      decision,
      reason_code,
      ROUND(COALESCE(detection_confidence,0),3) AS det,
      ROUND(COALESCE(ocr_confidence,0),3) AS ocr,
      ROUND((COALESCE(detection_confidence,0)+COALESCE(ocr_confidence,0))/2.0,3) AS combined,
      vote_confirmations,
      ROUND(COALESCE(vote_avg_confidence,0),3) AS vote_avg
    FROM recognition_events
    WHERE plate IN (?, ?)
    ORDER BY id DESC
    LIMIT 40
    """,
    TARGETS,
).fetchall()
for r in rows:
    print(dict(r))

print("\n=== Last 20 events overall ===")
rows = cur.execute(
    """
    SELECT id, occurred_at, plate, zone_name, decision, reason_code,
           ROUND(COALESCE(detection_confidence,0),3) AS det,
           ROUND(COALESCE(ocr_confidence,0),3) AS ocr,
           ROUND((COALESCE(detection_confidence,0)+COALESCE(ocr_confidence,0))/2.0,3) AS combined,
           vote_confirmations,
           ROUND(COALESCE(vote_avg_confidence,0),3) AS vote_avg
    FROM recognition_events
    ORDER BY id DESC
    LIMIT 20
    """
).fetchall()
for r in rows:
    print(dict(r))

print("\n=== Whitelist status for targets ===")
for plate in TARGETS:
    rows = cur.execute(
        """
        SELECT plate, fuzzy_plate, is_active, source, updated_at
        FROM whitelist_plates
        WHERE plate = ?
        LIMIT 5
        """,
        (plate,),
    ).fetchall()
    print(plate, [dict(x) for x in rows])

con.close()
