import sqlite3

conn = sqlite3.connect("data/inversiq.db")

conn.execute("""
UPDATE users
SET is_platform_admin = 1
WHERE email = 'dvanlieshout00@gmail.com'
""")

conn.commit()
conn.close()

print("done")