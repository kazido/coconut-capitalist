import mysql.connector

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="epick778"
)

cursor = db.cursor()

cursor.execute("SELECT * FROM users")

result = cursor.fetchall()

for x in result:
    print(x)
