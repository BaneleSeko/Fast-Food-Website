
import sqlite3

connection = sqlite3.connect("street_bites.db")

tables = connection.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
""").fetchall()

print("Database tables:")

for table in tables:
    print(f"\nTable: {table[0]}")

    rows = connection.execute(
        f'SELECT * FROM "{table[0]}" LIMIT 10'
    ).fetchall()

    for row in rows:
        print(row)

connection.close()
