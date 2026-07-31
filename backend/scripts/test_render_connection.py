import psycopg2

try:
    conn = psycopg2.connect(
        host="dpg-d96cbe5ckfvc73f9dda0-a.oregon-postgres.render.com",
        port=5432,
        user="dbuser",
        password="PhLP6N9FxdqakJ3EKfu9BZenNVXuiasPAgGmwNFi68FyH/ZirQlSve8TisH52b",
        dbname="supportai_9q4b",
        connect_timeout=5
    )
    print("SUCCESS CONNECTING TO RENDER POSTGRES!")
    conn.close()
except Exception as e:
    print(f"Failed to connect: {e}")
