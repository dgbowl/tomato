import sqlite3
import os

dbfile = r'C:\Users\krpe\AppData\Local\dgbowl\tomato\0.1.dev2\database.db'

conn = sqlite3.connect(dbfile)
cur = conn.cursor()
cur.execute(
    "UPDATE state SET sampleid = 'cell_2' WHERE pipeline = 'MPG2-6-2'"
)
conn.commit()
conn.close()