from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


db_url = "mysql+pymysql://root:Srushti%40123@localhost:3306/telusko" #engine means connection to the database
#engine creates connection that session uses
engine = create_engine(db_url)
#sessionlocal is like class, from this classs we create instances that is db sessions
# -Engine & session factory are created once when the app starts; they do not open a database connection.
# -A session is created per request, opens a DB connection only when a query runs, and
# - When the request finishes, the session is closed and the connection is returned to the pool.
SessionLocal = sessionmaker(
    autoflush=False,
    autocommit = False, 
    bind=engine
)

# App starts
#   ↓
# Engine created (no connection)
#   ↓
# Session factory created
#   ↓
# ---------------------------------
# Request comes
#   ↓
# Session created
#   ↓
# Query → DB connection opened
#   ↓
# Commit / Query
#   ↓
# Session closed
#   ↓
# Connection returned to pool
# ---------------------------------