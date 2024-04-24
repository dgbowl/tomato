import sqlite3
import os

dbfile = r"C:\Users\krpe\AppData\Local\dgbowl\tomato\0.1.dev2\database.db"

conn = sqlite3.connect(dbfile)
cur = conn.cursor()
cur.execute("UPDATE state SET ready = 1 WHERE pipeline = 'MPG2-6-1'")
conn.commit()
conn.close()
