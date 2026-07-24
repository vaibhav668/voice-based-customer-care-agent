import psycopg2

passwords = ["postgres", "admin", "root", "123456", "password", "supportai", ""]
for pwd in passwords:
    try:
        conn = psycopg2.connect(
            dbname="supportai",
            user="postgres",
            password=pwd,
            host="localhost",
            port=5432,
            connect_timeout=2
        )
        print(f"SUCCESS connecting to postgres with password: '{pwd}'")
        conn.close()
        break
    except Exception as e:
        print(f"Failed with password '{pwd}': {e}")
