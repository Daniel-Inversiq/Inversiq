import sqlite3

conn = sqlite3.connect("data/inversiq.db")
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE outbound_suggestions ADD COLUMN email_validation_result VARCHAR(50)")
except Exception as e:
    print("email_validation_result:", e)

try:
    cur.execute("ALTER TABLE outbound_suggestions ADD COLUMN is_deliverability_risky BOOLEAN NOT NULL DEFAULT 0")
except Exception as e:
    print("is_deliverability_risky:", e)

try:
    cur.execute("ALTER TABLE outbound_suggestions ADD COLUMN validation_reason TEXT")
except Exception as e:
    print("validation_reason:", e)

conn.commit()
conn.close()

print("done")