import os
 
if os.getenv("ENV", "DEV") in ["DEV", "TEST"]:
    from dotenv import load_dotenv
 
    load_dotenv(os.getenv("ENV_FILE", ".env"))
 
 
class Config:
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
 