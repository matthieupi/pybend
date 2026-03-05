"""N3TX Example Application — demonstrates the framework with a simple product catalog."""
import logging
import os
import sys

# Add src/ to path for development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import config
from n3tx.core.app import create_app
from n3tx.core.storage.sqlite_storage import SQLiteStorage
from models import User, Bot, Product, Comment, Like

# Configure logging for development
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

# Database path — resolve relative to this file so it's stable regardless of CWD
_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, config.SQLITE_DB_FILE)

# Create the application
storage = SQLiteStorage(DB_PATH)
app = create_app(
    models=[User, Product],
    join_models=[(Product, Comment), (Comment, Like), (Product, Like)],
    storage=storage,
    jwt_secret=config.JWT_SECRET,
    static_dir=os.path.join(os.path.dirname(__file__), 'static'),
    ssr="full",
    name="N3TX Example",
    version="0.8.0",
    description="Example product catalog with comments and likes",
)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
